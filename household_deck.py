"""One Deck per Household (docs/adr/0002-one-deck-per-household.md).

Curation is unchanged: build_guests.py still writes one `wrapped.json` (+ `pool.json`) per guest
under `site_guest/<guest_token>/`. This module bundles a Household's members into
`site_guest/h/<hh_token>/`:

  index.html        copy of app/bundle.html (the Deck loads ./household.json)
  household.json    {title, couple, members: [{cid, first, light, wrapped}], summary, face_src,
                     mode?: "light" (solo light guest only)}
  pool-<cid>.json   each member's all-photos pool, stripped and tagged like the shots
  faces/<cid>.jpg   this Household's crop of every non-member face the Deck shows

Every member `wrapped` goes through photo_rule.strip_wrapped (the Household-only rule), has its
image paths re-rooted one directory deeper (household._reroot), and every gallery shot, group-map
photo and pool entry gains `who`: the Household members in that photo. `summary` holds counts and
EventStats for every non-empty subset of members (≤4 members → ≤15 subsets), so the client never
has to recount a Selection.

Faces: a non-member's face (Your people costars, group members, group-map nodes) is cropped
per Household from a photo that includes a member of THIS Household (`face_src` records which
photo; photo_rule.violations checks it); none such → null and the app shows the initial. Members'
own faces and the couple's keep the site-wide img/face_<cid>.jpg.

No email address or guest id is ever read into these files: members carry cid, first name,
light flag and the (already PII-free) wrapped dict only.
"""
import html as _html
import json
import shutil
from itertools import combinations
from pathlib import Path

import household
import photo_rule

COUPLE_IDS = [15, 50]   # Neel, Preethi


def _covers_household(env):
    """An envelope name that plausibly names more than one person: has "&", " and " or "family"."""
    e = env.lower()
    return "&" in e or " and " in e or "family" in e


def deck_title(envelope, firsts):
    """Decision 2: guest-list envelope name when it plausibly covers the Household (any name for
    one member; for more, only one with "&", " and " or "family" — "Ursula Smith" on a two-person
    Household names one of them); else first names joined, ≥4 → first three & family."""
    env = (envelope or "").strip()
    if env and (len(firsts) <= 1 or _covers_household(env)):
        return env
    return " & ".join(firsts[:3]) + (" & family" if len(firsts) > 3 else "")


def subset_key(cids):
    return ",".join(str(c) for c in sorted(cids))


def _reroot_tree(node):
    """Every deck-relative path ('../…') one level deeper; everything else untouched."""
    if isinstance(node, str):
        return household._reroot(node) if node.startswith("../") else node
    if isinstance(node, dict):
        return {k: _reroot_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_reroot_tree(v) for v in node]
    return node


def _ids(m):
    return set(m.get("ids") or {m["cid"]})


def _who(pid, by_photo, members):
    faces = by_photo.get(pid, set()) if pid else set()
    return [m["cid"] for m in members if faces & _ids(m)]


def _pid_of(item, *keys):
    if item.get("id"):
        return item["id"]
    return next((p for p in (photo_rule._pid(item.get(k)) for k in keys) if p), None)


def _photo_frame(photos):
    if photos is None:
        import build_wrapped
        photos = build_wrapped.load_ctx()["photos"]
    return photos.drop_duplicates("photo_id").set_index("photo_id")[["gallery", "t"]]


def _summary(members, by_photo, photos):
    import build_wrapped
    frame = _photo_frame(photos)
    per = {m["cid"]: {pid for pid, faces in by_photo.items() if faces & _ids(m)} for m in members}
    out = {}
    cids = [m["cid"] for m in members]
    for r in range(1, len(cids) + 1):
        for sub in combinations(cids, r):
            pids = set().union(*(per[c] for c in sub))
            rows = frame.loc[frame.index.intersection(sorted(pids))].reset_index()
            events = build_wrapped.events_of(rows) if len(rows) else []
            out[subset_key(sub)] = dict(n_photos=len(pids), n_events=len(events), events=events)
    return out


FACE_DIR = "faces"


def _face_refs(w):
    """(holder dict, key) for every face reference in a member's wrapped."""
    for c in w.get("costars") or []:
        yield c, "img"
    for grp in w.get("groups") or []:
        for gm in grp.get("members") or []:
            yield gm, "face"
        for node in (grp.get("map") or {}).get("members") or []:
            yield node, "face"


def _localize_faces(out_members, hh_ids, couple, face_pick):
    """Point every non-member, non-couple face at this Household's crop (faces/<cid>.jpg) or None.
    face_pick(cid, hh_ids) -> the source photo id of a crop from a photo with ≥1 member, or None.
    Returns face_src {str(cid): photo_id}."""
    own = set(hh_ids) | set(couple)
    src = {}
    for m in out_members:
        for holder, key in _face_refs(m["wrapped"]):
            cid = holder.get("cid")
            if cid in own:
                continue
            if cid not in src:
                src[cid] = face_pick(cid, hh_ids) if face_pick else None
            holder[key] = f"{FACE_DIR}/{cid}.jpg" if src[cid] else None
    return {str(c): pid for c, pid in sorted(src.items()) if pid}


def build_household_json(members, by_photo, couple, title=None, photos=None, stats=None, face_pick=None):
    """household.json for one Household.

    members: [{cid, first, light, wrapped, ids?}] in display order; `ids` is the member's cluster
    plus merged fragments (default {cid}). couple: the couple's cluster ids incl. fragments.
    photos: frame with photo_id, gallery, t (default: build_wrapped's photos). stats: optional dict
    that receives the number of photos the rule removed under "removed".
    """
    hh_ids = set().union(*(_ids(m) for m in members)) if members else set()
    out_members, removed = [], 0
    for m in members:
        w, n = photo_rule.strip_wrapped(m["wrapped"], by_photo, hh_ids, couple)
        removed += n
        for g in w.get("gallery") or []:
            for s in g.get("shots") or []:
                s["who"] = _who(_pid_of(s, "url"), by_photo, members)
        for grp in w.get("groups") or []:
            for p in ((grp.get("map") or {}).get("photos") or []):
                p["who"] = _who(_pid_of(p, "l", "s"), by_photo, members)
        w.pop("slug", None)     # the member's own personal deck token (admin-only field)
        for grp in w.get("groups") or []:
            # a group member's url/slug is another guest's personal deck link; household.json is
            # publicly fetchable and the Deck never navigates there (photo_rule.leaked_tokens guards it)
            for gm in grp.get("members") or []:
                gm.pop("url", None); gm.pop("slug", None)
        out_members.append(dict(cid=m["cid"], first=m["first"], light=bool(m.get("light")),
                                wrapped=_reroot_tree(w)))
    if stats is not None:
        stats["removed"] = stats.get("removed", 0) + removed
    face_src = _localize_faces(out_members, hh_ids, couple, face_pick)
    out = dict(title=title if title is not None else deck_title("", [m["first"] for m in members]),
               couple=list(COUPLE_IDS), members=out_members,
               summary=_summary(members, by_photo, photos), face_src=face_src)
    if len(out_members) == 1 and out_members[0]["light"]:
        out["mode"] = "light"      # a light guest alone in their Household: Cover + couple picks + own gallery
    return out


def household_pool(pool, by_photo, members, couple):
    """A member's pool.json for the Household page: rule-stripped, re-rooted, `who`-tagged.
    Returns (pool, removed)."""
    hh_ids = set().union(*(_ids(m) for m in members))
    keep, removed = [], 0
    for p in (pool or {}).get("photos") or []:
        pid = photo_rule._pid(p.get("url"))
        if pid is None or not photo_rule.allowed(by_photo.get(pid, set()), hh_ids, couple):
            removed += 1
            continue
        keep.append(dict(_reroot_tree(p), who=_who(pid, by_photo, members)))
    return dict(photos=keep), removed


def write_household(dir, hh, bundle_html, pools=None, faces=None):
    """Write one Household's Deck: index.html (the bundle), household.json, pool-<cid>.json,
    faces/<cid>.jpg. `pools` maps cid → an already-stripped pool (household_pool); `faces` maps
    cid → a writer(out_path) for that face crop (one per hh["face_src"] entry)."""
    d = Path(dir)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(bundle_html, d / "index.html")
    (d / "household.json").write_text(json.dumps(hh, indent=1))
    for old in d.glob("pool-*.json"):
        old.unlink()
    for cid, pool in (pools or {}).items():
        (d / f"pool-{cid}.json").write_text(json.dumps(pool, indent=1))
    fd = d / FACE_DIR
    if fd.is_dir():
        shutil.rmtree(fd)
    if faces:
        fd.mkdir()
        for cid, write in faces.items():
            write(fd / f"{cid}.jpg")


def everyone_index(dir, entries):
    """The test address's page: every Household Deck as title + best photo + link.
    entries: [{title, hero, url}] with hero/url relative to this page."""
    cards = []
    for e in entries:
        title = _html.escape(e.get("title") or "")
        hero = _html.escape(e.get("hero") or "")
        href = _html.escape(e.get("url") or "")
        img = f'<img loading=lazy src="{hero}" alt="">' if hero else ""
        cards.append(f'<a class=card href="{href}">'
                     f'<span class=thumb>{img}</span>'
                     f'<span class=meta><span class=who>{title}</span></span>'
                     f'<span class=go>Open &rarr;</span></a>')
    d = Path(dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(household.render_page(
        "Everyone", f"Every Household&rsquo;s Deck &mdash; {len(entries)} in all.", "".join(cards)))
