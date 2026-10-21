"""
Build one person's Wrapped page data: site/<slug>/wrapped.json + the images it references.

CLI:    python build_wrapped.py --cluster 15 --name Neel [--slug neel] [--curated] [--site site]
Module: from build_wrapped import build, load_ctx
        build(cid, name, slug, curated=True, site_dir=Path("site_guest"))   # fast in a batch loop

Curated mode (guest release): the gallery section is ~25 hand-picked photos in buckets
(With the couple / You in focus / Group photos) from curation.pick_highlights, driven by
photo_people.parquet + per-person thresholds.json. Legacy mode (admin drafts): the gallery
is every distinct moment with alternate takes.

The page itself is the React bundle (app/bundle.html) copied next to wrapped.json by the
batch builders (build_top.py / build_guests.py); it renders standalone from ./wrapped.json.
"""
import argparse, json, re
from pathlib import Path
import numpy as np, pandas as pd, cv2
from PIL import Image

import curation
from curation import COUPLE, pick_highlights, thr_of, GRADE_MEDIUM_BAND, _bars
import guest_palette

HERE = Path(__file__).parent
CACHE, D = HERE / "cache", HERE / "data"
TIER_OVERRIDE = D / "tier_override.json"

# ---- experience tiers (issue #32 / DESIGN.md § Experience tiers) ----
def tier_by_count(n):
    return "inner" if n >= 150 else "group" if n >= 50 else "cameo" if n >= 15 else "glimpse"

def load_tier_overrides():
    """{cid_str: tier}. git-tracked veto file; keys starting with '_' are ignored."""
    if TIER_OVERRIDE.exists():
        raw = json.loads(TIER_OVERRIDE.read_text())
        out = {}
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            out[k] = v if isinstance(v, str) else v.get("tier")
        return out
    return {}

def tier_of(cid, n_photos, overrides=None):
    ov = overrides if overrides is not None else load_tier_overrides()
    return ov.get(str(cid)) or tier_by_count(n_photos)

def graph_tier_of(n_ties):
    """Connection gate (DESIGN.md) — overrides the tier table for the graph/finder section."""
    return "finder" if n_ties >= 4 else "face_row" if n_ties >= 2 else "pair" if n_ties >= 1 else "none"
PHOTOG_URL = "https://example.pixieset.com"   # TODO(user): confirm the guest-facing gallery URL
COUPLE_NAME, DATES = "Preethi & Neel", "April 24–25, 2026"
EVENT_ORDER = ["GREH SHANTI", "HALDI", "SANGEET", "GROOM MORNING", "BRIDE MORNING", "COUPLE SHOOT", "WEDDING", "RECEPTION COUPLE", "RECEPTION PARTY"]
EVENT_NICE = {"GREH SHANTI": "Greh Shanti", "HALDI": "Haldi", "SANGEET": "Sangeet", "GROOM MORNING": "Groom's morning", "BRIDE MORNING": "Bride's morning",
              "COUPLE SHOOT": "Couple shoot", "WEDDING": "Wedding", "RECEPTION COUPLE": "Reception portraits", "RECEPTION PARTY": "Reception"}
BUCKET_NICE = {"focus": "You in focus", "with_couple": f"With {COUPLE_NAME}", "group": "Group photos", "more": "More from the weekend"}
BUCKET_ORDER = ["focus", "with_couple", "group", "more"]
MOMENTS = {15: ["Haldi entrance — Sadi Gali, 9:50 AM", "Sangeet entrance — Mauja Hi Mauja", "The shoe game", "Preethi & Neel dance — Sangeet", "Reception entrance — Beautiful Now", "First dance", "Cake cutting", "The speech"],
           50: ["Haldi entrance — Sadi Gali, 9:50 AM", "Preethi & friends dance — Haldi", "Preethi & the moms dance", "Sangeet entrance — Mauja Hi Mauja", "The shoe game", "Sibling dance with Sean", "Preethi & Neel dance — Sangeet", "First dance", "Cake cutting", "The speech"]}

_ctx = {}
def load_ctx():
    """Load shared frames once (safe to call repeatedly; batch builders rely on this)."""
    if _ctx: return _ctx
    labels = json.loads((D / "labels.json").read_text()) if (D / "labels.json").exists() else {}
    faces = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
    photos = pd.read_parquet(D / "photos.parquet").merge(pd.read_parquet(D / "photo_features.parquet"), on="photo_id")
    photos["t"] = pd.to_datetime(photos.taken_at, format="%Y:%m:%d %H:%M:%S", errors="coerce")
    pp, wc = curation.load_photo_people(D)
    ppl = faces[(faces.det_score >= .65) & (faces["size"] >= 60)].groupby("photo_id").cluster_id.apply(frozenset)
    # "our picks": best couple shots, shared by every page
    both = faces[faces.cluster_id.isin(COUPLE)].groupby("photo_id").cluster_id.nunique()
    cp = photos[photos.photo_id.isin(set(both[both == 2].index)) & (photos.n_faces <= 3)].copy()
    cp["score"] = cp.sharpness.rank(pct=True)
    picks = cp.sort_values("score", ascending=False).groupby("gallery").head(2).sort_values("t")
    picks = picks[picks.gallery.isin(["HALDI", "SANGEET", "WEDDING", "COUPLE SHOOT", "RECEPTION COUPLE", "RECEPTION PARTY"])].head(10)
    manual = D / "our_picks.json"   # hand-curated by the couple at /picks — overrides the auto list
    couple_picks = (json.loads(manual.read_text()) or list(picks.photo_id)) if manual.exists() else list(picks.photo_id)
    # telemetry endpoint (issue #39): read-if-exists like tokens.json; absent -> beacon no-ops client-side
    tf = D / "telemetry.json"
    telemetry = json.loads(tf.read_text()) if tf.exists() else None
    _ctx.update(labels=labels, faces=faces, photos=photos, pp=pp, wc=wc, ppl=ppl, couple_picks=couple_picks,
                tier_overrides=load_tier_overrides(), palette_overrides=guest_palette.load_overrides(),
                telemetry=telemetry)
    return _ctx

def name_of(cid, labels):
    l = labels.get(str(cid), {})
    if l.get("status") == "not_guest": return None
    if l.get("status") == "merged": l = labels.get(str(l.get("merge_into")), {})
    return l.get("first") or l.get("name")

def union_ids(cid, labels):
    """This cluster + clusters merged into it + clusters labeled as the same guest."""
    me = labels.get(str(cid), {}); ids = {cid}
    for c, l in labels.items():
        if l.get("status") == "merged" and str(l.get("merge_into")) == str(cid): ids.add(int(c))
        if me.get("guest_id") is not None and l.get("guest_id") == me.get("guest_id") and l.get("status") == "labeled": ids.add(int(c))
    return ids

def crop_face(f, out):
    """The 240px face crop every face chip uses: face box f (photo_id, x1, y1, x2, y2) widened
    by half a box each side, 0.6 above, written as JPEG q85 to `out`."""
    img = cv2.imread(str(CACHE / f.photo_id)); H, W = img.shape[:2]; bw, bh = f.x2 - f.x1, f.y2 - f.y1
    x1, y1, x2, y2 = int(max(0, f.x1 - .5 * bw)), int(max(0, f.y1 - .6 * bh)), int(min(W, f.x2 + .5 * bw)), int(min(H, f.y2 + .5 * bh))
    cv2.imwrite(str(out), cv2.resize(img[y1:y2, x1:x2], (240, 240)), [cv2.IMWRITE_JPEG_QUALITY, 85])

def events_of(df):
    """EventStat list (app/src/types.ts) for a frame with one row per photo: photo_id, gallery, t.

    The single definition of per-event counts and times — a guest's deck and a Household's
    per-Selection summary (household_deck.py) both go through it.
    """
    by_ev = df.groupby("gallery").agg(n=("photo_id", "count"), first=("t", "min"), last=("t", "max"))
    by_ev = by_ev.reindex([e for e in EVENT_ORDER if e in by_ev.index])
    return [dict(key=e, name=EVENT_NICE.get(e, e.title()), n=int(r.n), first=r.first.strftime("%-I:%M %p"), last=r.last.strftime("%-I:%M %p"),
                 day=r.first.strftime("%a %b %-d"), pct=int(100 * r.n / by_ev.n.max())) for e, r in by_ev.iterrows()]

def build(cid, name, slug, curated=True, site_dir=None, draft=False, gap=120, jac=0.34, env="prod"):
    ctx = load_ctx(); labels, faces, photos, pp, wc, ppl = ctx["labels"], ctx["faces"], ctx["photos"], ctx["pp"], ctx["wc"], ctx["ppl"]
    site = Path(site_dir) if site_dir else HERE / "site"
    img_dir = site / "img"; (site / slug).mkdir(parents=True, exist_ok=True); img_dir.mkdir(parents=True, exist_ok=True)

    my_ids = union_ids(cid, labels)
    mine = faces[faces.cluster_id.isin(my_ids)].sort_values("det_score", ascending=False).drop_duplicates("photo_id")
    mine = mine.merge(photos, on=["photo_id", "gallery"]).sort_values("t").reset_index(drop=True)
    # hero scoring: reuse precomputed per-face sharpness from photo_people (no image reads)
    mine = mine.merge(pp[["face_id", "face_sharp"]], on="face_id", how="left")
    mine["face_sharp"] = mine.face_sharp.fillna(0.0)
    rank = lambda s: s.rank(pct=True)
    mine["hscore"] = 0.40 * rank(mine.face_sharp) + 0.25 * rank(mine.det_score) + 0.20 * rank(mine["size"]) + 0.15 * rank(mine.sharpness)

    # scenes over my photos (for the "distinct moments" stat + legacy gallery)
    mine["ppl_set"] = mine.photo_id.map(ppl).apply(lambda s: s if isinstance(s, frozenset) else frozenset())
    scene, cur, last = [], -1, None
    for r in mine.itertuples():
        new = last is None or r.gallery != last.gallery or (r.t - last.t).total_seconds() > gap or \
              len(r.ppl_set & last.ppl_set) / max(1, len(r.ppl_set | last.ppl_set)) < jac
        cur += int(new); scene.append(cur); last = r
    mine["scene"] = scene

    # stats / timeline
    events = events_of(mine)
    peak = max(events, key=lambda e: e["n"])

    # co-stars: labeled people only (guests must never see "Guest #id")
    co = faces[faces.photo_id.isin(mine.photo_id) & ~faces.cluster_id.isin(my_ids) & (faces.det_score >= 0.65) & (faces["size"] >= 36)]
    co_counts = co.groupby("cluster_id").photo_id.nunique().sort_values(ascending=False)
    costars = []
    for c, n in co_counts.items():
        nm = name_of(int(c), labels)
        if not nm: continue
        f = co[co.cluster_id == c].sort_values("det_score", ascending=False).iloc[0]
        out = img_dir / f"face_{int(c)}.jpg"
        if not out.exists(): crop_face(f, out)
        # `couple` lets the deck exclude the bride/groom from the "most photographed with"
        # stat: they are in nearly every guest's photos, so they would win it for almost
        # everyone and say nothing. Beat 5 ("You & the couple") is already theirs.
        costars.append(dict(cid=int(c), n=int(n), name=nm, img=f"../img/face_{int(c)}.jpg", labeled=True,
                            couple=bool(int(c) in COUPLE)))
        if len(costars) >= 6: break

    # hero: best large-face solo shot (fallback: <=2 faces)
    solo = mine[(mine.n_faces == 1) & (mine["size"] >= 120)].sort_values("hscore", ascending=False)
    hero_pool = solo if len(solo) >= 3 else mine[(mine.n_faces <= 2)].sort_values("hscore", ascending=False)
    hero = hero_pool.iloc[0] if len(hero_pool) else mine.sort_values("hscore", ascending=False).iloc[0]

    def emit(photo_id, side, sub):
        dst = img_dir / sub / photo_id; dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            im = Image.open(CACHE / photo_id); im.thumbnail((side, side), Image.LANCZOS); im.save(dst, quality=82, optimize=True)
        return f"../img/{sub}/{photo_id}"

    photo_t = photos.set_index("photo_id").t
    fpos = {r.photo_id: (round(100 * (r.x1 + r.x2) / 2 / r.w, 1), round(100 * (r.y1 + r.y2) / 2 / r.h, 1)) for r in mine.itertuples()}

    # courtesy flag (issue #34): a downloadable photo is courtesy-grade when another prominent
    # third party in it (prom >= 0.4, face >= 48px) grades 'bad' vs their own bar (margin < -15).
    # "Download all" excludes these by default; they stay individually selectable.
    _bar = _bars()
    def _courtesy_set(photo_ids):
        oth = pp[pp.photo_id.isin(photo_ids) & (~pp.cluster_id.isin(my_ids)) & (pp.prom >= 0.4) & (pp["size"] >= 48)].copy()
        if not len(oth): return set()
        oth["margin"] = oth.score - oth.cluster_id.map(_bar).fillna(oth.score)
        return set(oth[oth.margin < -GRADE_MEDIUM_BAND].photo_id.unique())
    courtesy_set = _courtesy_set(set(mine.photo_id))
    ev_nice = lambda pid: EVENT_NICE.get(photos.loc[photos.photo_id == pid, "gallery"].iloc[0], str(photos.loc[photos.photo_id == pid, "gallery"].iloc[0]).title())
    # merged clusters -> treat as one person for the picker AND the pool zoner (issue #39)
    dfu = pp if len(my_ids) == 1 else pp.assign(cluster_id=pp.cluster_id.map(lambda c: cid if c in my_ids else c))
    thr = thr_of(cid)[0]
    if curated:
        picks, meta = pick_highlights(cid, dfu, wc, thr)
        seen, by_bucket = set(), {}
        for p in picks:
            if p["photo_id"] in seen: continue
            seen.add(p["photo_id"]); by_bucket.setdefault(p["bucket"], []).append(p)
        gallery = []
        for b in BUCKET_ORDER:
            if b not in by_bucket: continue
            shots = []
            for p in by_bucket[b]:
                emit(p["photo_id"], 500, "s")
                ph = photos[photos.photo_id == p["photo_id"]].iloc[0]
                fx, fy = fpos.get(p["photo_id"], (50, 50))
                shots.append(dict(url=emit(p["photo_id"], 1400, "l"), s=emit(p["photo_id"], 500, "s"), thumbs=[], n_alt=0,
                                  fx=fx, fy=fy, time=photo_t[p["photo_id"]].strftime("%-I:%M %p"), portrait=bool(ph.h > ph.w),
                                  id=p["photo_id"], event=EVENT_NICE.get(ph.gallery, str(ph.gallery).title()),
                                  bucket=b, courtesy=bool(p["photo_id"] in courtesy_set)))
            nice = ("Together" if cid in COUPLE and b == "with_couple" else BUCKET_NICE.get(b, b))
            gallery.append(dict(name=nice, shots=shots, n_all=int(meta["roles"].get(b, len(shots))) if b in ("focus", "group") else len(shots)))
        # section hygiene: a section with <3 shots isn't a section — fold into its neighbour
        MIN_SECTION = 3
        tidy, pending = [], []
        for g in gallery:
            if len(g["shots"]) < MIN_SECTION:
                pending.extend(g["shots"])
            else:
                g["shots"] = pending + g["shots"] if pending and not tidy else g["shots"]
                if pending and tidy: tidy[-1]["shots"].extend(pending)
                pending = []
                tidy.append(g)
        if pending:
            if tidy: tidy[-1]["shots"].extend(pending)
            else: tidy = [dict(name="Your weekend", shots=pending, n_all=len(pending))]
        gallery = tidy
        n_picks = sum(len(g["shots"]) for g in gallery)
    else:
        best = mine.loc[mine.groupby("scene").hscore.idxmax()]
        alts = mine.groupby("scene").photo_id.apply(list).to_dict()
        gallery = []
        for e in [x["key"] for x in events]:
            shots = [dict(url=emit(r.photo_id, 1400, "l"), s=emit(r.photo_id, 500, "s"),
                          thumbs=[emit(p, 500, "s") for p in alts[r.scene] if p != r.photo_id][:8],
                          n_alt=len(alts[r.scene]) - 1, fx=fpos.get(r.photo_id, (50, 50))[0], fy=fpos.get(r.photo_id, (50, 50))[1],
                          time=r.t.strftime("%-I:%M %p"), portrait=bool(r.h > r.w),
                          id=r.photo_id, event=EVENT_NICE.get(e, str(e).title()), bucket="event",
                          courtesy=bool(r.photo_id in courtesy_set))
                     for r in best[best.gallery == e].itertuples()]
            gallery.append(dict(name=EVENT_NICE.get(e, e), shots=shots, n_all=int(by_ev.loc[e, "n"])))
        n_picks = None

    hfx, hfy = fpos.get(hero.photo_id, (50, 50))
    n_photos = int(len(mine))

    # ---- tier (issue #32) + derived palette tokens (issue #31) + connection gate ----
    tier = tier_of(cid, n_photos, ctx.get("tier_overrides"))
    tokens = guest_palette.build_tokens(cid, pp, my_ids, override=(ctx.get("palette_overrides") or {}).get(str(cid)))
    n_ties = sum(1 for c in costars if c.get("n", 0) >= 2)   # labeled co-stars with a real tie (>=2 shared photos)
    graph_tier = graph_tier_of(n_ties)

    # ---- full pool (issue #39): every photo of the guest, zoned for the all-photos tab ----
    # Courtesy-grade photos are EXCLUDED entirely (arch review #40): the below-bar zone must
    # never ship another person at their worst — only the guest's own quality-hidden photos.
    shown_ids = {hero.photo_id} | {s["id"] for g in gallery for s in g["shots"]}
    mypp = dfu[dfu.cluster_id == cid].sort_values("score", ascending=False).drop_duplicates("photo_id").set_index("photo_id")
    pool_photos = []
    for r in mine.sort_values(["t", "photo_id"]).itertuples():
        pid = r.photo_id
        if pid in courtesy_set: continue
        row = mypp.loc[pid] if pid in mypp.index else None
        weak = row is None or bool(row.role == "background" or row.blink == 1 or row.edge == 1 or row.score < thr)
        zone = "shown" if pid in shown_ids else ("below_bar" if weak else "skipped")
        emit(pid, 500, "s")
        pool_photos.append(dict(url=emit(pid, 1400, "l"), zone=zone,
                                rank=round(float(row.look_rank), 3) if row is not None else 0.0))
    assert not any(p["url"].split("/img/l/")[-1] in courtesy_set for p in pool_photos), "courtesy photo leaked into pool"
    n_pool = len(pool_photos)

    out = dict(name=name, slug=slug, cluster=int(cid), hero=emit(hero.photo_id, 1600, "l"), hero_fx=hfx, hero_fy=hfy,
               hero_event=EVENT_NICE.get(hero.gallery, str(hero.gallery).title()),
               n_photos=n_photos, n_events=len(events), n_scenes=int(mine.scene.nunique()),
               n_hidden=int(len(mine) - mine.scene.nunique()), peak=peak, events=events, costars=costars,
               moments=MOMENTS.get(cid, []), gallery=gallery, picks=[emit(p, 1400, "l") for p in ctx["couple_picks"]],
               couple=COUPLE_NAME, dates=DATES, gallery_link=PHOTOG_URL, from_us=None,
               draft=bool(draft), curated=bool(curated), n_picks=n_picks,
               tier=tier, guest_accent=tokens["guest_accent"], guest_support=tokens["guest_support"],
               accent_ink=tokens["accent_ink"], n_ties=n_ties, graph_tier=graph_tier, n_pool=n_pool)
    if ctx.get("telemetry"):
        out["telemetry"] = dict(url=ctx["telemetry"]["url"], key=ctx["telemetry"]["anon_key"], env=env)
    (site / slug / "wrapped.json").write_text(json.dumps(out, indent=1))
    (site / slug / "pool.json").write_text(json.dumps(dict(photos=pool_photos), indent=1))
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", type=int, required=True); ap.add_argument("--name", required=True); ap.add_argument("--slug")
    ap.add_argument("--curated", action="store_true"); ap.add_argument("--site", default=None); ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    slug = a.slug or re.sub(r"\W+", "-", a.name.lower()).strip("-")
    o = build(a.cluster, a.name, slug, curated=a.curated, site_dir=a.site, draft=a.draft)
    print(f"{a.name}: {o['n_photos']} photos, {o['n_scenes']} scenes" + (f", {o['n_picks']} curated picks in {len(o['gallery'])} buckets" if a.curated else ""))
