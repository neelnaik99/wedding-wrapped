"""
Build the deployable guest site: one curated Wrapped deck per labeled guest at an
unguessable token URL, plus a neutral landing page. Output tree (default site_guest/):

  site_guest/
    index.html          neutral landing (no links, no bundle)
    robots.txt, _headers
    <token>/index.html  app bundle (standalone deck mode)
    <token>/wrapped.json
    h/<token>/index.html      one Deck per Household (app bundle; loads ./household.json)
    h/<token>/household.json  every member's wrapped dict, rule-stripped + who-tagged (household_deck.py)
    h/<token>/pool-<cid>.json each member's all-photos pool, same treatment
    img/{l,s}/..., img/face_*.jpg   shared images (only what pages reference)

Also writes (all gitignored):
  data/tokens.json         stable guest_id -> token map (read-if-exists; links never break)
  data/send_manifest.json  per-guest {name, guest_id, token, url, email, party, n_photos, hub_url}
                           (hub_url = the guest's Household Deck, set for every guest)
  data/households.json     per-household {key, token, url, title, members}

Usage: python build_guests.py [--site site_guest] [--base-url https://<project>.pages.dev] [--check] [--only CID]
                              [--guests ~/Downloads/guest-list.csv]   (envelope names → Deck titles)
"""
import argparse, csv, json, os, re, secrets, shutil, sys, time
from pathlib import Path
import build_wrapped
import household
import household_deck
import photo_rule

HERE = Path(__file__).parent; D = HERE / "data"
TOKENS = D / "tokens.json"; MANIFEST = D / "send_manifest.json"
BUNDLE = HERE / "app" / "bundle.html"
COUPLE_IDS = [15, 50]   # Neel, Preethi
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"   # base32 minus ambiguous 0/1/l/o

LANDING = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta name=robots content="noindex,nofollow"><title>Preethi &amp; Neel</title>
<style>body{margin:0;min-height:100dvh;display:flex;align-items:center;justify-content:center;background:#1a0f12;color:#f7efe6;font:17px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;text-align:center;padding:24px}
h1{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-weight:500;font-size:34px;margin:0 0 10px}p{color:#c9b3a6;max-width:34ch;margin:0 auto}
form{display:flex;flex-direction:column;gap:12px;margin:24px auto 0;max-width:320px}
input{font:inherit;padding:14px 16px;border-radius:12px;border:1px solid #5a4339;background:#2c1d20;color:#f7efe6}
button{font:inherit;font-weight:600;padding:14px;border:0;border-radius:999px;background:#b8862b;color:#1a0f12;cursor:pointer}
button:disabled{opacity:.6}#done a{color:#f2c14e;text-decoration:none;white-space:nowrap}#done{display:none;margin-top:24px}#done p+p{margin-top:12px;font-size:15px}</style>
</head><body><div><h1>Preethi &amp; Neel</h1><p>Enter your email and we&rsquo;ll send you a link to your photos from the wedding.</p>
<form id=f><input id=e type=email name=email autocomplete=email required placeholder="you@example.com" aria-label="Email">
<button id=b type=submit>Send my link</button></form>
<div id=done><p>If we have that email, your link is on its way.</p><p>Check your spam folder too. Didn&rsquo;t get it in 5 minutes? Text Neel at <a href="sms:+15555550123">+1-555-555-0123</a>.</p></div></div>
<script>document.getElementById("f").addEventListener("submit",async ev=>{ev.preventDefault();const b=document.getElementById("b");b.disabled=true;
try{await fetch("/api/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({email:document.getElementById("e").value})})}catch(_){}
document.getElementById("f").style.display="none";document.getElementById("done").style.display="block"})</script>
</body></html>"""

def write_root(site):
    """Site-root files: the Login page (what the Card points to), /login alias, crawler + header rules."""
    site = Path(site)
    (site / "index.html").write_text(LANDING)
    (site / "_redirects").write_text("/login / 301\n")
    (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (site / "_headers").write_text("/*\n  X-Robots-Tag: noindex\n  Referrer-Policy: no-referrer\n")

def _mint(tokens, key):
    if key not in tokens:
        tokens[key] = "".join(secrets.choice(ALPHABET) for _ in range(10))
    return tokens[key]


def _deck_url(base_url, tok):
    path = f"/{household.HUB_DIR}/{tok}/"
    return f"{base_url.rstrip('/')}{path}" if base_url else path


class HouseholdFaces:
    """Per-Household face crops (household_deck._localize_faces): a non-member's face on a Deck
    is cropped from that person's best face (confident detection, then largest, then det_score)
    in a photo that also includes ≥1 member of that Household. Crop params: build_wrapped.crop_face.

    faces: frame with photo_id, cluster_id, x1, y1, x2, y2, size, det_score.
    by_photo: photo_id -> cluster ids (photo_people, the same map the photo rule checks).
    ids_of: cid -> that person's cluster ids incl. merged fragments."""

    def __init__(self, faces, by_photo, ids_of):
        f = faces.assign(_conf=faces.det_score >= 0.65)
        self._rows = {int(c): g for c, g in f.groupby("cluster_id")}
        self._by_photo, self._ids_of, self._chosen = by_photo, ids_of, {}

    def pick(self, cid, hh_ids):
        ids = set(self._ids_of(cid))
        parts = [self._rows[c] for c in ids if c in self._rows]
        if not parts:
            return None
        import pandas as pd
        cand = pd.concat(parts).sort_values(["_conf", "size", "det_score"], ascending=False)
        for r in cand.itertuples():
            there = self._by_photo.get(r.photo_id, set())
            if there & hh_ids and there & ids:
                self._chosen[(cid, frozenset(hh_ids))] = r
                return r.photo_id
        return None

    def writers(self, face_src, hh_ids):
        """{cid: writer(out_path)} for a Household's face_src (cids as household.json keys them)."""
        key = frozenset(hh_ids)
        return {int(c): (lambda out, r=self._chosen[(int(c), key)]: build_wrapped.crop_face(r, out))
                for c in face_src}


def build_household_decks(site, manifest, tokens, base_url, by_photo, ids_of, couple, envelopes,
                          photos=None, bundle_html=BUNDLE, stats=None, faces=None):
    """One Deck per Household, one-person Households included (ADR 0002).

    Reads each member's site/<token>/{wrapped,pool}.json (the curation output), writes
    site/h/<hh_token>/ via household_deck, and sets every member's `hub_url` to the Deck URL.
    Mints `hh:<key>` into `tokens` only when missing (never re-mints); the caller persists them.
    ids_of: cid -> that guest's cluster ids incl. merged fragments. envelopes: {hh_key: name}.
    faces: a HouseholdFaces for non-member face crops (None → those faces are null).
    Returns [{key, token, url, title, hero, members: [guest tokens], ids}] (ids = Household cids).
    """
    site = Path(site)
    decks = []
    for key, rows in sorted(household.households(manifest).items()):
        tok = _mint(tokens, f"hh:{key}")
        members = []
        for m in rows:
            gdir = site / m["token"]
            members.append(dict(cid=m["cluster"], first=m["first"], light=(m.get("tier") == "light"),
                                wrapped=json.loads((gdir / "wrapped.json").read_text()),
                                ids=set(ids_of.get(m["cluster"], {m["cluster"]}))))
        hh = household_deck.build_household_json(
            members, by_photo, couple, title=household_deck.deck_title(envelopes.get(key, ""), [m["first"] for m in rows]),
            photos=photos, stats=stats, face_pick=faces.pick if faces else None)
        hh_ids = set().union(*(mm["ids"] for mm in members))
        pools = {}
        for m, row in zip(members, rows):
            pf = site / row["token"] / "pool.json"
            if pf.exists():
                pools[m["cid"]], n = household_deck.household_pool(json.loads(pf.read_text()), by_photo, members, couple)
                if stats is not None: stats["removed"] = stats.get("removed", 0) + n
        household_deck.write_household(site / household.HUB_DIR / tok, hh, bundle_html, pools=pools,
                                       faces=faces.writers(hh["face_src"], hh_ids) if faces else None)
        url = _deck_url(base_url, tok)
        for m in rows: m["hub_url"] = url
        decks.append(dict(key=key, token=tok, url=url, title=hh["title"],
                          hero=hh["members"][0]["wrapped"].get("hero") or "",
                          members=[m["token"] for m in rows],
                          ids=sorted(set().union(*(mm["ids"] for mm in members)))))
    return decks


def everyone_page(site, decks, tokens, base_url):
    """One private index listing every Household Deck, for the test address only
    (make_emails --everyone-email). Mints `hh:__everyone__` on first build; the caller persists tokens."""
    tok = _mint(tokens, "hh:__everyone__")
    entries = [dict(title=d["title"], hero=d["hero"], url=f"../{d['token']}/")
               for d in sorted(decks, key=lambda d: d["title"].lower())]
    household_deck.everyone_index(Path(site) / household.HUB_DIR / tok, entries)
    return dict(token=tok, url=_deck_url(base_url, tok))


def guest_envelopes(path):
    """{hh_key: envelope name} from the guest CSV; {} (with a warning) when the file is missing."""
    p = Path(os.path.expanduser(path))
    if not p.exists():
        print(f"WARNING: guest list {p} not found — Deck titles fall back to first names (pass --guests)")
        return {}
    with open(p, newline="") as f:
        return household.envelope_names(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site_guest"); ap.add_argument("--base-url", default="")
    ap.add_argument("--check", action="store_true"); ap.add_argument("--only", type=int)
    ap.add_argument("--env", choices=["prod", "stage"], default="prod",
                    help="telemetry env stamped into each deck (issue #39); use stage for --branch stage deploys")
    ap.add_argument("--guests", default="~/Downloads/guest-list.csv",
                    help="guest-list CSV; its `envelope name` titles each Household Deck")
    a = ap.parse_args()
    site = HERE / a.site; site.mkdir(exist_ok=True)
    labels = json.loads((D / "labels.json").read_text())
    tokens = json.loads(TOKENS.read_text()) if TOKENS.exists() else {}
    # the per-member explorer namespace (gx:<group_id>:<cid> -> "x"+10) is retired: the map is a
    # deck route now, so those URLs no longer resolve. Prune them so the namespace stays honest.
    dead = [k for k in tokens if k.startswith("gx:")]
    if dead:
        for k in dead: del tokens[k]
        TOKENS.write_text(json.dumps(tokens, indent=1))
        print(f"pruned {len(dead)} retired gx: explorer token(s)")
    stats = {}
    import pandas as pd
    pp = pd.read_parquet(D / "photo_people.parquet")
    photos_per = pp.groupby("cluster_id").photo_id.nunique().to_dict()

    # one deck per guest: dedupe labeled clusters by guest_id (largest cluster wins)
    people = {}
    for cid, l in labels.items():
        if l.get("status") != "labeled": continue
        key = f"gid:{l['guest_id']}" if l.get("guest_id") is not None else f"cluster:{cid}"
        if key not in people or photos_per.get(int(cid), 0) > photos_per.get(people[key]["cid"], 0):
            people[key] = dict(cid=int(cid), label=l)
    print(f"{len(people)} guests to build (from {sum(1 for l in labels.values() if l.get('status')=='labeled')} labeled clusters)")

    manifest, thin = [], []
    cameo_pending = []   # tokens to render as postcards after group payloads are injected (issue #32)
    prior = {m["token"]: m for m in json.loads(MANIFEST.read_text())} if MANIFEST.exists() else {}
    FULL_DECK = {"inner", "group"}   # tiers that always receive the React deck bundle.
    # cameo -> postcard UNLESS the connection gate upgrades them (DESIGN.md § Experience tiers:
    # "the connection gate overrides the tier table — combination finder at 4+ real ties, even
    # for a cameo"). The map lives inside the deck now, so a cameo with a map needs the bundle;
    # that is only knowable after group payloads exist, so the surface is decided below.
    # glimpse -> no own link.
    for key, p in sorted(people.items(), key=lambda kv: -photos_per.get(kv[1]["cid"], 0)):
        cid, l = p["cid"], p["label"]
        if a.only and cid != a.only: continue
        if key not in tokens:
            tokens[key] = "".join(secrets.choice(ALPHABET) for _ in range(10))
            TOKENS.write_text(json.dumps(tokens, indent=1))
        tok = tokens[key] if isinstance(tokens[key], str) else tokens[key]["token"]
        first = l.get("first") or l.get("name", "").split(" ")[0]
        out = build_wrapped.build(cid, first, tok, curated=True, site_dir=site, draft=False, env=a.env)
        tier = out["tier"]
        # send rule (DESIGN.md § Experience tiers): full deck for inner/group, postcard for cameo,
        # no own link for glimpse (they live in a household deck / a personal email instead).
        if tier in FULL_DECK:
            shutil.copy(HERE / "app" / "bundle.html", site / tok / "index.html")
        elif tier == "cameo":
            cameo_pending.append(tok)                # surface decided after group injection
        # glimpse: intentionally no index.html — no standalone page
        if (out["n_picks"] or 0) < 10: thin.append((cid, l.get("name"), out["n_picks"]))
        manifest.append(dict(name=l.get("name"), first=first, guest_id=l.get("guest_id"), cluster=cid, token=tok,
                             url=f"{a.base_url.rstrip('/')}/{tok}/" if a.base_url else f"/{tok}/",
                             email=l.get("email", ""), party=l.get("party", ""), n_photos=out["n_photos"], n_picks=out["n_picks"],
                             tier=tier, link=(tier != "glimpse"), hero=out["hero"], graph_tier=out["graph_tier"],
                             upgraded=False))   # set below when the connection gate upgrades a cameo to the deck
        print(f"  {l.get('name'):28} #{cid:<5} {out['n_photos']:4} photos → {out['n_picks']:2} picks  [{tier}]  /{tok}/", flush=True)

    # ---- inject group payloads (your-people section: members, together-counts, lookup links, mini-map) ----
    import cv2
    from itertools import combinations
    from collections import Counter
    gf = D / "groups.json"
    groups = json.loads(gf.read_text())["groups"] if gf.exists() else []
    if groups:
        prim = {}
        for key, per in people.items():
            for c in build_wrapped.union_ids(per["cid"], labels): prim[c] = per["cid"]
        sub = pp[pp.cluster_id.isin(prim)].copy(); sub["pc"] = sub.cluster_id.map(prim)
        sets = sub.groupby("photo_id").pc.apply(set)
        pair = Counter(t for s_ in sets for t in combinations(sorted(s_), 2))
        tog = lambda a, b: int(pair.get(tuple(sorted((a, b))), 0))
        by_cid = {m["cluster"]: m for m in manifest}
        faces_df = None
        def ensure_face(c):
            nonlocal faces_df
            out = site / "img" / f"face_{c}.jpg"
            if out.exists(): return f"../img/face_{c}.jpg"
            import pandas as pd2
            if faces_df is None:
                faces_df = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
            ff = faces_df[faces_df.cluster_id == c].sort_values("det_score", ascending=False)
            if not len(ff): return None
            build_wrapped.crop_face(ff.iloc[0], out)
            return f"../img/face_{c}.jpg"
        COUPLE_IDS = [15, 50]
        # ---- per-MEMBER group map payloads (viewer-scoped: every photo includes the viewer) ----
        from group_explorer import member_map_payload
        from PIL import Image
        photos_df = pd.read_parquet(D / "photos.parquet")
        pgal = photos_df.set_index("photo_id")
        def emit_img(pid, side, subdir):
            dst = site / "img" / subdir / pid; dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                im = Image.open(HERE / "cache" / pid); im.thumbnail((side, side), Image.LANCZOS); im.save(dst, quality=82, optimize=True)
            return f"../img/{subdir}/{pid}"
        # stale cleanup: the map now lives inside the deck (#/map), so every standalone explorer
        # dir is dead — the old group-level ones (g+10) and the per-member ones (x+10) alike.
        import re as _re, shutil as _sh
        for dd in site.iterdir():
            if dd.is_dir() and _re.fullmatch(r"[gx][a-z2-9]{10}", dd.name): _sh.rmtree(dd)
        member_map = {}   # (gid, cid) -> viewer-scoped map payload
        phsets_all = sub.groupby("photo_id").agg(mem=("pc", lambda x: sorted(set(x))), look=("look", "mean"))
        all_sets = sub.groupby("photo_id").pc.apply(set)
        looks = sub.sort_values("look", ascending=False).drop_duplicates(["photo_id", "pc"]).set_index(["photo_id", "pc"])[["look", "blink", "edge", "score"]].sort_index()
        import curation as _cur; _bars_map = {int(k): float(v["value"]) for k, v in _cur.thresholds().items()}
        for g in groups:
            gm = [c for c in COUPLE_IDS + sorted(g["members"]) if c in by_cid]
            if len([c for c in gm if c not in COUPLE_IDS]) < 2: continue
            gset = set(gm)
            ph = phsets_all[phsets_all.mem.map(lambda m: len(gset.intersection(m)) >= 2)].copy()
            ph["gmem"] = ph.mem.map(lambda m: sorted(gset.intersection(m)))
            keep = set()
            for u, v in combinations(sorted(gm), 2):
                cand = ph[ph.gmem.map(lambda m, _u=u, _v=v: _u in m and _v in m)]
                keep |= set(cand.sort_values("look", ascending=False).head(8).index)
            pool = ph.loc[sorted(keep)]
            mem_info = [dict(cid=c, name=by_cid[c]["name"], first=by_cid[c]["first"], face=ensure_face(c)) for c in gm if ensure_face(c)]
            edges = [[u, v, int(pair.get(tuple(sorted((u, v))), 0))] for u, v in combinations(sorted(gm), 2) if pair.get(tuple(sorted((u, v))), 0) >= 2]
            # shared metas for the whole pool once (emit images once)
            metas_all = {}
            for pid, r in pool.iterrows():
                pr = pgal.loc[pid]
                metas_all[pid] = dict(id=pid, s=emit_img(pid, 500, "s"), l=emit_img(pid, 1400, "l"),
                                      t=str(pr.taken_at)[11:16], gallery=str(pr.gallery).title(), mem=[int(c) for c in r.gmem])
            n_pages = 0
            for c in gm:
                # quality-visibility: viewer must grade >= medium; photos where another member grades bad are rationed to <=20%
                bar_c = _bars_map.get(c, 0.0)
                def _grades(meta):
                    try: vs = float(looks.loc[(meta["id"], c)].score)
                    except KeyError: return None
                    if vs < bar_c - 15: return None          # viewer below medium: never shown to them
                    worst = 0.0
                    for oc in meta["mem"]:
                        if oc == c: continue
                        try: om = float(looks.loc[(meta["id"], oc)].score) - _bars_map.get(oc, 0.0)
                        except KeyError: continue
                        worst = min(worst, om)
                    return (vs - bar_c, worst)
                graded = []
                for meta in metas_all.values():
                    if c not in meta["mem"]: continue
                    g_ = _grades(meta)
                    if g_ is not None: graded.append((g_, meta))
                graded.sort(key=lambda t: (t[0][1] < -15, -(t[0][0])))   # others-bad last, then viewer quality
                cap_bad = max(2, int(0.2 * len(graded)))
                mine_metas, bad_used = [], 0
                for (vm, worst), meta in graded:
                    if worst < -15:
                        if bad_used >= cap_bad: continue
                        bad_used += 1
                    # courtesy flag (issue #34): another member in-frame grades 'bad' for this viewer
                    mine_metas.append(dict(meta, courtesy=bool(worst < -15)))
                # "and of course yourself": their best solo shots (no other group member in frame)
                solo_ids = [pid for pid, s_ in all_sets.items() if c in s_ and len(gset.intersection(s_)) == 1]
                solo_rows = []
                for pid in solo_ids:
                    try: lr = looks.loc[(pid, c)]
                    except KeyError: continue
                    if int(lr.blink) == 0 and int(lr.edge) == 0: solo_rows.append((float(lr.look), pid))
                solo_rows.sort(reverse=True)
                for _, pid in solo_rows[:12]:
                    pr = pgal.loc[pid]
                    mine_metas.append(dict(id=pid, s=emit_img(pid, 500, "s"), l=emit_img(pid, 1400, "l"),
                                           t=str(pr.taken_at)[11:16], gallery=str(pr.gallery).title(), mem=[int(c)], courtesy=False))
                mine_metas.sort(key=lambda m: (m["gallery"], m["t"]))
                member_map[(g["id"], int(c))] = member_map_payload(g["name"], int(c), mem_info, mine_metas, edges)
                n_pages += 1
            print(f"  map: {g['name']:36} {n_pages} member payloads, pool {len(metas_all)} photos", flush=True)
        n_injected = 0
        for m in manifest:
            me = m["cluster"]
            mine_groups = groups if me in COUPLE_IDS else [g for g in groups if me in g["members"]]
            payload = []
            for g in mine_groups:
                ids = [c for c in COUPLE_IDS + sorted(g["members"]) if c != me and c in by_cid]
                members = []
                for c in ids:
                    fc = ensure_face(c)
                    if fc is None: continue
                    members.append(dict(cid=c, name=by_cid[c]["name"], first=by_cid[c]["first"], face=fc,
                                        together=tog(me, c), url=f"/{by_cid[c]['token']}/"))
                # DESIGN.md face-chip rule + #13: top members first, by photos-together desc then name asc
                members.sort(key=lambda mm: (-mm["together"], mm["name"]))
                if members:
                    payload.append(dict(id=g["id"], name=g["name"], members=members, map=member_map.get((g["id"], me))))
            wj = site / m["token"] / "wrapped.json"
            d = json.loads(wj.read_text()); d["groups"] = payload
            wj.write_text(json.dumps(d, indent=1)); n_injected += 1 if payload else 0
        print(f"group payloads injected into {n_injected} decks ({len(groups)} groups defined)")

        # ---- build-time assertion (#13): any guest with >=1 real group tie MUST carry a groups payload ----
        # Root cause of the original bug: the couple (COUPLE_IDS) are implicit members of every group but
        # appear in NO group's `members` list, so the generic `[g for g in groups if me in g['members']]`
        # path yielded an empty groups array for them. The `me in COUPLE_IDS -> all groups` branch fixes
        # it; this assertion guards against that (and any future) regression by re-reading the written files.
        expect = {}
        for m in manifest:
            me = m["cluster"]
            mgs = groups if me in COUPLE_IDS else [g for g in groups if me in g["members"]]
            n = sum(1 for g in mgs if any(c != me and c in by_cid and ensure_face(c)
                                          for c in COUPLE_IDS + list(g["members"])))
            if n: expect[m["token"]] = (m["name"], me, n)
        missing = [(nm, me, n) for tok2, (nm, me, n) in expect.items()
                   if not json.loads((site / tok2 / "wrapped.json").read_text()).get("groups")]
        if missing:
            raise SystemExit(f"BUILD FAIL (#13): {len(missing)} guest(s) belong to >=1 group but their "
                             f"wrapped.json has no groups payload: {missing[:8]}")
        for ccid in COUPLE_IDS:
            if ccid in by_cid:
                assert json.loads((site / by_cid[ccid]["token"] / "wrapped.json").read_text()).get("groups"), \
                    f"BUILD FAIL (#13): couple deck #{ccid} missing groups payload"
        print(f"assertion OK (#13): {len(expect)} group-connected decks carry groups; couple covered")

    # ---- households + the send rule for glimpse guests (issue #32 / DESIGN.md § Experience tiers) ----
    # NOTE: the "Also seen" strip and joint cover are RENDERED by the React deck (app/**, WS-Deck's file);
    # here we only emit the payload (also_seen / cover_names) into the household head's wrapped.json.
    from collections import defaultdict as _dd
    by_token = {m["token"]: m for m in manifest}
    parties = _dd(list)
    for m in manifest:
        if m.get("party"): parties[m["party"]].append(m)
    also_seen_by_head, glimpse_personal = _dd(list), set()
    for m in manifest:
        if m["tier"] != "glimpse": continue
        mates = [x for x in parties.get(m.get("party"), []) if x["token"] != m["token"] and x.get("link")]
        head = max(mates, key=lambda x: x["n_photos"]) if mates else None
        if head: also_seen_by_head[head["token"]].append(m)
        else: glimpse_personal.add(m["token"])
    for htok, seen in also_seen_by_head.items():
        wj = site / htok / "wrapped.json"; d = json.loads(wj.read_text())
        d["also_seen"] = [dict(cid=s["cluster"], name=s["name"], first=s["first"], best_photo=s["hero"]) for s in seen]
        head = by_token[htok]
        if len(parties.get(head.get("party"), [])) == 2 and len(seen) == 1:   # 2-person couple household -> joint cover
            d["cover_names"] = f"{head['first']} & {seen[0]['first']}"
        wj.write_text(json.dumps(d, indent=1))
    # glimpse-with-no-household -> personal email (make_emails builds it from manifest tier/link/personal_email)
    for m in manifest:
        m["personal_email"] = (m["tier"] == "glimpse" and m["token"] in glimpse_personal)
    if any(m["tier"] == "glimpse" for m in manifest):
        print(f"households: {sum(len(v) for v in also_seen_by_head.values())} glimpse guest(s) into 'Also seen' "
              f"strips, {len(glimpse_personal)} flagged for personal emails")

    # ---- cameo surface (issue #32 + the one-link rule): deck if the connection gate upgraded
    # them, postcard otherwise. A cameo carrying a group map has 2+ real ties in that group and
    # the map is a deck route (#/map), so the postcard physically cannot host it — upgrading is
    # the only way that guest reaches their map without a second URL.
    if cameo_pending:
        import postcard
        upgraded = []
        for tok2 in cameo_pending:
            d = json.loads((site / tok2 / "wrapped.json").read_text())
            if any(g.get("map") for g in d.get("groups", [])):
                shutil.copy(HERE / "app" / "bundle.html", site / tok2 / "index.html")
                upgraded.append(tok2)
            else:
                postcard.build_postcard(site / tok2, d)
        for m in manifest:
            if m["token"] in upgraded: m["upgraded"] = True
        print(f"cameo surfaces: {len(upgraded)} upgraded to the full deck (they carry a group map), "
              f"{len(cameo_pending) - len(upgraded)} postcards rendered")

    write_root(site)
    if a.only:   # merge the rebuilt guest(s) into the existing manifest
        for m in manifest: prior[m["token"]] = m
        manifest = sorted(prior.values(), key=lambda m: -m["n_photos"])
    # ---- one Deck per Household (ADR 0002): every Household, one-person ones included ----
    ids_of = {m["cluster"]: build_wrapped.union_ids(m["cluster"], labels) for m in manifest}
    couple = set().union(*(build_wrapped.union_ids(c, labels) for c in COUPLE_IDS))
    by_photo = {pid: set(int(c) for c in cs) for pid, cs in pp.groupby("photo_id").cluster_id}
    hub_dir = site / household.HUB_DIR
    # the deploy guard's inputs belong to one finished build: drop the old pair now, write the new
    # pair only after this build's own checks pass (a build that dies in between leaves none)
    (D / "household_guard.json").unlink(missing_ok=True)
    (hub_dir / ".build_id").unlink(missing_ok=True)
    rule = {}
    _uid = {}
    def any_ids(c):
        if c not in _uid: _uid[c] = build_wrapped.union_ids(c, labels)
        return _uid[c]
    face_rows = pd.read_parquet(D / "faces.parquet").merge(
        pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
    hh_faces = HouseholdFaces(face_rows, by_photo, any_ids)
    decks = build_household_decks(site, manifest, tokens, a.base_url, by_photo, ids_of, couple,
                                  guest_envelopes(a.guests), photos=build_wrapped.load_ctx()["photos"], stats=rule,
                                  faces=hh_faces)
    everyone = everyone_page(site, decks, tokens, a.base_url)
    TOKENS.write_text(json.dumps(tokens, indent=1))
    (D / "everyone_hub.json").write_text(json.dumps(everyone))
    # stale pages: a Household that lost its guests keeps its token in tokens.json but must not
    # keep a live page -- the URL was already sent to somebody.
    live = {d["token"] for d in decks} | {everyone["token"]}
    for dd in hub_dir.iterdir():
        if dd.is_dir() and dd.name not in live: shutil.rmtree(dd)
    (D / "households.json").write_text(json.dumps(
        [{k: v for k, v in d.items() if k not in ("ids", "hero")} for d in decks], indent=1))
    from collections import Counter as _Counter
    sizes = _Counter(len(d["members"]) for d in decks)
    print(f"{len(decks)} Household Decks → {hub_dir}/ (sizes: "
          + ", ".join(f"{n}×{k}" for k, n in sorted(sizes.items())) + f"); rule stripped {rule.get('removed', 0)} photo reference(s)")
    # the build fails closed: no Household page may show a photo without a member (or only the couple)
    bad = photo_rule.violations(site, by_photo, {**{d["token"]: set(d["ids"]) for d in decks},
                                                 everyone["token"]: set()}, couple)
    bad += photo_rule.leaked_tokens(site, {v for k, v in tokens.items() if not k.startswith("hh:")})
    print(f"{len(bad)} rule violations")
    if bad:
        for v in bad[:10]: print("  VIOLATION", v)
        sys.exit(1)
    # PII contract (deploy_site.sh greps the same): data files and the everyone page only --
    # the Deck index.html is the app bundle, whose admin code names the guest_id field.
    pii = [f for f in list(hub_dir.glob("*/*.json")) + [hub_dir / everyone["token"] / "index.html"]
           if re.search(r"guest_id|[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", f.read_text())]
    if pii:
        sys.exit(f"BUILD FAIL: email address or guest id under {hub_dir}: {[str(f) for f in pii[:5]]}")

    # what deploy_site.sh needs to re-run the rule from disk (photo_rule.py --check): one artifact,
    # tied to this site by build_id. The person-token set rides along so the deploy scan never
    # reads a tokens.json that may be older or newer than the site.
    build_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(4)}"
    (D / "household_guard.json").write_text(json.dumps(
        dict(build_id=build_id, couple=sorted(couple),
             households={**{d["token"]: d["ids"] for d in decks}, everyone["token"]: []},
             person_tokens=sorted(v for k, v in tokens.items() if not k.startswith("hh:")))))
    (hub_dir / ".build_id").write_text(build_id)

    MANIFEST.write_text(json.dumps(manifest, indent=1))
    print(f"\n{len(manifest)} decks → {site}")
    if thin: print("THIN DECKS (<10 picks — consider lowering their threshold):", thin)

    if a.check:
        files = [f for f in site.rglob("*") if f.is_file()]
        big = [f for f in files if f.stat().st_size > 20 * 1024 * 1024]
        # Stray deck folders: anything holding a wrapped.json that no manifest row claims.
        # Hand-made test decks (e.g. a "xtestneel00" scratch copy) carry draft:false, so neither
        # the image check nor deploy_site.sh's draft grep sees them -- they would ship as live,
        # guessable pages holding a real guest's photos. Nothing legitimate is unclaimed, so a
        # stray is always either a test artifact or a guest deleted from labels (the --only
        # pruning gap in docs/OPEN-ISSUES.md). Fail and let a human delete it.
        claimed = {m["token"] for m in manifest}
        stray = sorted(d.name for d in site.iterdir()
                       if d.is_dir() and (d / "wrapped.json").exists() and d.name not in claimed)
        missing = []
        for m in manifest:
            w = json.loads((site / m["token"] / "wrapped.json").read_text())
            for u in [w["hero"]] + w["picks"] + [s["url"] for g in w["gallery"] for s in g["shots"]] + [c["img"] for c in w["costars"]]:
                if not (site / u.replace("../", "")).exists(): missing.append((m["token"], u))
            # issue #39: every full deck ships a pool.json, and both image sizes exist for every pool entry
            pf = site / m["token"] / "pool.json"
            if m["tier"] in FULL_DECK:
                assert pf.exists(), f"missing pool.json for /{m['token']}/"
                for p in json.loads(pf.read_text())["photos"]:
                    for u in (p["url"], p["url"].replace("/img/l/", "/img/s/")):
                        if not (site / u.replace("../", "")).exists(): missing.append((m["token"], u))
        # Household Decks: every image they reference resolves from one directory deeper than a deck
        for d in decks:
            hd = hub_dir / d["token"]
            assert (hd / "index.html").exists() and (hd / "household.json").exists(), f"missing Deck /{household.HUB_DIR}/{d['token']}/"
            for f in hd.glob("*.json"):
                text = f.read_text()
                for u in set(re.findall(r'"(\.\./\.\./img/[^"]+)"', text)):
                    if not (site / u.replace("../", "")).exists(): missing.append((f"{household.HUB_DIR}/{d['token']}", u))
                for u in set(re.findall(r'"(faces/[^"]+)"', text)):
                    if not (hd / u).exists(): missing.append((f"{household.HUB_DIR}/{d['token']}", u))
        total = sum(f.stat().st_size for f in files)
        print(f"CHECK: {len(files)} files ({'OK' if len(files) < 20000 else 'OVER 20K LIMIT'}), {total/1e6:.0f} MB, files>20MB: {len(big)}, missing images: {len(missing)}, stray decks: {len(stray)}")
        if missing[:5]: print("  e.g.", missing[:5])
        if stray: print(f"  STRAY DECK FOLDERS (not in the manifest -- delete them): {stray}")
        print(f"CHECK: {len(decks)} Household Deck(s), all pages present")
        assert len(files) < 20000 and not big and not missing and not stray, "CHECK FAILED"
        print("CHECK PASSED")

if __name__ == "__main__":
    main()
