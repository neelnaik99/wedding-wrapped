"""
Interactive naming stage: put a guest-list name on every face cluster.

  python label_server.py [--min 15] [--port 8792] [--guests ~/Downloads/guest-list.csv]

Open http://localhost:8792  (works from a phone on the same Wi-Fi too — hand it to the moms).
Keys:  Enter = assign · ↑/↓ pick · ⌘/Ctrl+→ skip · ⌘/Ctrl+← back · ⌘/Ctrl+. not-a-guest · ⌘/Ctrl+/ merge into first similar · ⌘/Ctrl+⌫ clear  (plain letters always type)
Writes data/labels.json  { "<cluster_id>": {name, first, last, email, party, guest_id, status:"labeled"} | {status:"not_guest"} | {status:"merged", merge_into} }
"""
import argparse, json, csv, os, re, threading, io, time, shutil
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote
import numpy as np, pandas as pd, cv2, importlib.util, sys

ap = argparse.ArgumentParser(); ap.add_argument("--min", type=int, default=15); ap.add_argument("--port", type=int, default=8792)
ap.add_argument("--guests", default="~/Downloads/guest-list.csv"); a = ap.parse_args()
HERE = Path(__file__).parent; D, CACHE = HERE / "data", HERE / "cache"; CROPS = D / "crops"; CROPS.mkdir(exist_ok=True)
LABELS = D / "labels.json"; HIST = D / "labels_history.jsonl"; BAK = D / "backups"; BAK.mkdir(exist_ok=True); lock = threading.Lock()
# startup backup (keep last 30)
if LABELS.exists():
    shutil.copy(LABELS, BAK / f"labels-{time.strftime('%Y%m%d-%H%M%S')}.json")
    for old in sorted(BAK.glob("labels-*.json"))[:-30]: old.unlink()
EVENT_COL = {"GREH SHANTI": "grah shanti", "HALDI": "haldi", "SANGEET": "mehendi & sangeet", "WEDDING": "wedding", "RECEPTION PARTY": "reception",
             "RECEPTION COUPLE": "reception", "BRIDE MORNING": "wedding", "GROOM MORNING": "wedding", "COUPLE SHOOT": "wedding"}

# ---- data --------------------------------------------------------------------------
faces = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
faces = faces[(faces.det_score >= .65) & (faces["size"] >= 36)]
photos = pd.read_parquet(D / "photos.parquet")
stats = pd.read_csv(D / "people_stats.csv", index_col=0)
exclude = set(json.loads((D / "exclude.json").read_text())) if (D / "exclude.json").exists() else set()
queue = [int(c) for c in stats.index if stats.loc[c, "photos"] >= a.min and c not in exclude]

guests = []
with open(os.path.expanduser(a.guests), newline="") as f:
    for i, r in enumerate(csv.DictReader(f)):
        ev = {k: bool(r.get(v, "").strip().lower().startswith("attending")) for k, v in
              {"GREH SHANTI": "grah shanti", "HALDI": "haldi", "SANGEET": "mehendi & sangeet", "WEDDING": "wedding", "RECEPTION PARTY": "reception"}.items()}
        guests.append(dict(id=i, first=r["first name"].strip(), last=r["last name"].strip(), email=r.get("email", "").strip(), party=r.get("party", ""),
                           envelope=r.get("envelope name", ""), events=ev, name=f'{r["first name"].strip()} {r["last name"].strip()}'.strip()))

# cluster centroids → similar clusters (for merge suggestions)
cl = faces[faces.cluster_id.isin(set(stats.index[stats.photos >= 5]))]
cent = {c: np.mean(np.stack(g.emb.values), axis=0) for c, g in cl.groupby("cluster_id")}
cids = list(cent); M = np.stack([cent[c] for c in cids]); M /= np.linalg.norm(M, axis=1, keepdims=True); S = M @ M.T
similar = {c: [(int(cids[j]), float(S[i, j])) for j in np.argsort(-S[i])[1:6] if S[i, j] > 0.35] for i, c in enumerate(cids)}

def load_labels():
    return json.loads(LABELS.read_text()) if LABELS.exists() else {}
def save_labels(lb):
    tmp = LABELS.with_suffix(".tmp"); tmp.write_text(json.dumps(lb, indent=1, ensure_ascii=False)); tmp.replace(LABELS)
def log_change(cid, before, after, who="ui"):
    with HIST.open("a") as f: f.write(json.dumps(dict(ts=time.strftime("%Y-%m-%dT%H:%M:%S"), cid=int(cid), before=before, after=after, who=who), ensure_ascii=False) + "\n")
def set_label(cid, new):
    """new=None clears. Returns (before, after). Caller holds lock."""
    lb = load_labels(); cid = str(cid); before = lb.get(cid)
    if new is None: lb.pop(cid, None)
    else: lb[cid] = new
    save_labels(lb); log_change(cid, before, new); return before, new
def labels_csv():
    lb = load_labels(); out = io.StringIO(); w = csv.writer(out)
    w.writerow(["cluster_id", "photos", "status", "name", "first", "last", "email", "party", "guest_id", "merge_into", "provisional"])
    for cid in sorted(lb, key=lambda c: -int(stats.loc[int(c), "photos"]) if int(c) in stats.index else 0):
        l = lb[cid]; w.writerow([cid, int(stats.loc[int(cid), "photos"]) if int(cid) in stats.index else "", l.get("status", ""), l.get("name", ""), l.get("first", ""), l.get("last", ""),
                                 l.get("email", ""), l.get("party", ""), l.get("guest_id", ""), l.get("merge_into", ""), int(bool(l.get("provisional")))])
    return out.getvalue()

SITE = HERE / "site"; APP_BUNDLE = HERE / "app" / "bundle.html"
_graph_cache = {}
def graph_json(min_photos):
    key = (min_photos, LABELS.stat().st_mtime if LABELS.exists() else 0)
    if key not in _graph_cache:
        _graph_cache.clear(); argv = sys.argv; sys.argv = ["x"]
        spec = importlib.util.spec_from_file_location("rg", HERE / "relationship_graph.py"); rg = importlib.util.module_from_spec(spec); spec.loader.exec_module(rg); sys.argv = argv
        R = rg.build(min_photos, faces_as_uri=False)
        for n in R["nodes"]: n["img"] = "/crop/" + quote(n["img"][6:], safe="")
        _graph_cache[key] = R
    return _graph_cache[key]

_co = {"mtime": 0}
def _cooccurrence():
    """(pair_counts, photos_per_primary, cluster->primary) over labeled people, hub math done on primary clusters."""
    mt = LABELS.stat().st_mtime if LABELS.exists() else 0
    if _co.get("mtime") != mt:
        from itertools import combinations
        from collections import Counter
        lb = load_labels()
        prim = {}
        for c, l in lb.items():
            if l.get("status") == "labeled":
                key = l.get("guest_id")
                prim[int(c)] = int(c)
        # merge: merged clusters -> target; same guest_id -> largest cluster
        sizes = faces.groupby("cluster_id").photo_id.nunique()
        by_gid = {}
        for c, l in lb.items():
            if l.get("status") == "labeled" and l.get("guest_id") is not None:
                by_gid.setdefault(l["guest_id"], []).append(int(c))
        for gid_, cs in by_gid.items():
            main = max(cs, key=lambda c: sizes.get(c, 0))
            for c in cs: prim[c] = main
        for c, l in lb.items():
            if l.get("status") == "merged": prim[int(c)] = prim.get(int(l["merge_into"]), int(l["merge_into"]))
        sub = faces[faces.cluster_id.isin(prim)].copy(); sub["pc"] = sub.cluster_id.map(prim)
        sets = sub.groupby("photo_id").pc.apply(set)
        _co["pairs"] = Counter(t for s_ in sets for t in combinations(sorted(s_), 2))
        _co["nphotos"] = sub.groupby("pc").photo_id.nunique().to_dict()
        _co["sets"] = sets.to_dict()
        _co["pgal"] = photos.set_index("photo_id").gallery.to_dict()
        _co["prim"] = prim; _co["mtime"] = mt
    return _co["pairs"], _co["nphotos"], _co["prim"]

PARTY_EV = {"SANGEET", "RECEPTION PARTY"}; CEREMONY_EV = {"GREH SHANTI", "WEDDING", "HALDI"}
def _group_tag(mem, pairs, nphotos):
    """Classify a proposed group by tightness (mean pairwise affinity) + event profile of internal co-occurrence."""
    from itertools import combinations
    ms = sorted(mem)[:20]
    affs = []
    for a1, b1 in combinations(ms, 2):
        t = pairs.get((a1, b1), 0)
        affs.append(min(t / nphotos.get(a1, 1), t / nphotos.get(b1, 1)) if t else 0.0)
    density = sum(affs) / max(1, len(affs))
    gal = {}
    memset = set(mem)
    for pid, s_ in _co.get("sets", {}).items():
        if len(s_ & memset) >= 2:
            g = _co["pgal"].get(pid); gal[g] = gal.get(g, 0) + 1
    tot = sum(gal.values()) or 1
    party = sum(v for k, v in gal.items() if k in PARTY_EV) / tot
    ceremony = sum(v for k, v in gal.items() if k in CEREMONY_EV) / tot
    n_ev = len(gal)
    tight = "tight" if density >= 0.12 else ("medium" if density >= 0.05 else "loose")
    if len(mem) <= 7 and density >= 0.12 and ceremony >= 0.4: kind = "nuclear family"
    elif len(mem) <= 7 and density >= 0.12: kind = "close friends"
    elif party >= 0.55: kind = "friend group"
    elif ceremony >= 0.55: kind = "family / community circle"
    elif n_ev <= 2 and density < 0.05: kind = "table / one-event acquaintances"
    else: kind = "mixed circle"
    where = "party-heavy" if party >= 0.55 else ("ceremony-heavy" if ceremony >= 0.55 else f"{n_ev} events")
    return f"looks like: {kind} — {tight}, {where}"

def name_map():
    lb = load_labels(); return {int(c): l.get("name") for c, l in lb.items() if l.get("name") and l.get("status") != "not_guest"}

def shared_photos(cids, event=None, limit=400):
    """photos containing ALL of cids (usable faces). Returns chronological list with boxes for every labeled/known face in the photo."""
    sets = [set(faces[faces.cluster_id == c].photo_id) for c in cids]
    ids = set.intersection(*sets) if sets else set()
    ph = photos[photos.photo_id.isin(ids)]
    if event: ph = ph[ph.gallery == event]
    ph = ph.sort_values("taken_at").head(limit)
    nm = name_map(); out = []
    fsub = faces[faces.photo_id.isin(ph.photo_id)]
    for r in ph.itertuples():
        ff = fsub[fsub.photo_id == r.photo_id]
        out.append(dict(photo_id=r.photo_id, url=f"/cache/{quote(r.photo_id)}", gallery=r.gallery, taken_at=r.taken_at, w=int(r.w), h=int(r.h),
                        faces=[dict(cid=int(f.cluster_id), name=nm.get(int(f.cluster_id)), box=[round(f.x1), round(f.y1), round(f.x2), round(f.y2)]) for f in ff.itertuples()]))
    return dict(count=len(ids), photos=out, by_event={k: int(v) for k, v in photos[photos.photo_id.isin(ids)].groupby("gallery").size().items()})

def wrapped_list():
    out = []
    for j in sorted(SITE.glob("*/wrapped.json")):
        d = json.loads(j.read_text()); out.append(dict(slug=d["slug"], name=d["name"], cluster=d["cluster"], n_photos=d["n_photos"], n_events=d["n_events"], n_scenes=d["n_scenes"], hero=d["hero"].replace("../", "/site/")))
    return sorted(out, key=lambda x: -x["n_photos"])

from curation import pick_highlights, thresholds, thr_of, load_photo_people, BUDGET_HL, THRESH, COUPLE
_pp = {"mtime": 0, "df": None, "wc": None}
def photo_people():
    """lazy-load photo_people.parquet + with-couple map (via curation.py)"""
    f = D / "photo_people.parquet"
    if not f.exists(): return None, None
    mt = f.stat().st_mtime
    if mt != _pp["mtime"]:
        _pp["df"], _pp["wc"] = load_photo_people(D); _pp["mtime"] = mt
    return _pp["df"], _pp["wc"]
def breakdown(pid, df, nm):
    ff = df[df.photo_id == pid].sort_values("size", ascending=False)
    th = thresholds()
    return [dict(cid=int(r.cluster_id), name=nm.get(int(r.cluster_id)), role=r.role, prom=round(float(r.prom), 2), score=float(r.score),
                 thr=(th.get(str(int(r.cluster_id))) or {}).get("value"), look_rank=round(float(r.look_rank), 2),
                 blink=int(r.blink), edge=int(r.edge), eye=(None if pd.isna(r.eye) else round(float(r.eye), 2)), smile=(None if pd.isna(r.smile) else round(float(r.smile), 2)),
                 face=f"/crop/{quote(r.face_id, safe='')}", box=None) for r in ff.itertuples()]

def crop(face_id, size=160, pad=.45):
    out = CROPS / (re.sub(r"[^\w.-]", "_", face_id) + f"_{size}.jpg")
    if not out.exists():
        f = faces[faces.face_id == face_id].iloc[0]
        img = cv2.imread(str(CACHE / f.photo_id)); H, W = img.shape[:2]; bw, bh = f.x2 - f.x1, f.y2 - f.y1
        x1, y1, x2, y2 = int(max(0, f.x1 - pad * bw)), int(max(0, f.y1 - pad * 1.2 * bh)), int(min(W, f.x2 + pad * bw)), int(min(H, f.y2 + pad * bh))
        cv2.imwrite(str(out), cv2.resize(img[y1:y2, x1:x2], (size, size)), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out

def cluster_payload(cid):
    lb = load_labels(); mine = faces[faces.cluster_id == cid]
    top = mine.sort_values("det_score", ascending=False).drop_duplicates("photo_id").head(18)
    ev = mine.groupby("gallery").photo_id.nunique().sort_values(ascending=False)
    ctx = top.head(4)  # a few full photos for context
    co = faces[faces.photo_id.isin(mine.photo_id) & (faces.cluster_id != cid)].groupby("cluster_id").photo_id.nunique().sort_values(ascending=False).head(6)
    def nm(c):
        l = lb.get(str(c), {}); return l.get("name") if l.get("status") == "labeled" or l.get("name") else None
    costars = []
    for c, n in co.items():
        f = faces[faces.cluster_id == c].sort_values("det_score", ascending=False).iloc[0]
        costars.append(dict(cid=int(c), n=int(n), name=nm(c), face=f"/crop/{quote(f.face_id, safe='')}"))
    sims = [dict(cid=c, sim=round(s, 2), name=nm(c), photos=int(stats.loc[c, "photos"]) if c in stats.index else 0,
                 face=f"/crop/{quote(faces[faces.cluster_id == c].sort_values('det_score', ascending=False).iloc[0].face_id, safe='')}") for c, s in similar.get(cid, [])]
    return dict(cid=cid, photos=int(stats.loc[cid, "photos"]), events={k: int(v) for k, v in ev.items()},
                faces=[dict(crop=f"/crop/{quote(r.face_id, safe='')}", photo=f"/cache/{quote(r.photo_id)}", box=[r.x1, r.y1, r.x2, r.y2], gallery=r.gallery) for r in top.itertuples()],
                context=[dict(url=f"/cache/{quote(r.photo_id)}", box=[r.x1, r.y1, r.x2, r.y2], gallery=r.gallery) for r in ctx.itertuples()],
                costars=costars, similar=sims, label=lb.get(str(cid)))

def _groups_with_together(groups_list):
    """Attach a per-member `together` map to each group: for each member, the number of photos
    that member shares with the rest of the group's (non-couple) members. Reuses the _cooccurrence()
    per-photo `sets` so the chip ordering in the admin Groups view is server-driven (#4)."""
    try:
        _cooccurrence()
        prim = _co.get("prim", {}); sets_ = _co.get("sets", {})
    except Exception:
        prim, sets_ = {}, {}
    out = []
    for g in groups_list:
        members = [int(m) for m in g.get("members", [])]
        pmap = {m: int(prim.get(m, m)) for m in members}           # cluster -> primary cluster
        basis = {pc for pc in pmap.values() if pc not in (15, 50)}  # couple excluded from co-occurrence basis
        counts = {}
        if len(basis) >= 2 and sets_:
            for s_ in sets_.values():
                inter = s_ & basis
                if len(inter) >= 2:
                    for pc in inter: counts[pc] = counts.get(pc, 0) + 1
        together = {str(m): int(counts.get(pmap[m], 0)) for m in members}
        out.append(dict(g, together=together))
    return out

# ---- pre-send review queue (issue #33) ------------------------------------------------
# Flags guests whose experience tier or derived accent might be a misfire, so they can be
# eyeballed in minutes before decks are sent. Reuses the SAME tier + palette code the build
# uses: build_wrapped.tier_of / union_ids (experience-tier cut points) and guest_palette
# (per-guest accent/support derivation + its fallback path). Decisions are written into the
# very files build_guests.py consumes — data/tier_override.json and data/palette_override.json —
# plus a small review_state.json that only tracks which flags a human has signed off on.
REVIEW_STATE = D / "review_state.json"          # {cid: {reviewed: bool, ts}} — sign-off ledger (not consumed by the build)
PALETTE_OVERRIDE = D / "palette_override.json"   # {cid: {accent, support, ink}} — read by guest_palette.load_overrides
TIER_OVERRIDE = D / "tier_override.json"         # {cid: "inner|group|cameo|glimpse|light"} — read by build_wrapped.load_tier_overrides
TIER_BOUNDARIES = (15, 50, 150)                  # DESIGN.md experience-tier cut points (glimpse<15, cameo, group, inner>=150)
VALID_TIERS = ("inner", "group", "cameo", "glimpse", "light")   # light: Neel-marked only; never computed from photo count
REVIEW_BAND = 15                                 # a photo count within +-this of a boundary is "near a boundary"
_rev = {"sig": None, "rows": None}               # cache of the expensive per-guest palette pass

def _bw():
    """Lazy handle to build_wrapped — reuses its tier_of / union_ids / load_tier_overrides."""
    import build_wrapped
    return build_wrapped

def _mtime(p):
    return p.stat().st_mtime if p.exists() else 0

def load_review_state():
    return json.loads(REVIEW_STATE.read_text()) if REVIEW_STATE.exists() else {}
def save_review_state(st):
    tmp = REVIEW_STATE.with_suffix(".tmp"); tmp.write_text(json.dumps(st, indent=1, ensure_ascii=False)); tmp.replace(REVIEW_STATE)

def _review_guest_cids():
    """One representative cluster per guest: labeled clusters deduped by guest_id, largest cluster
    wins (mirrors build_guests.py so the queue matches exactly who gets a deck)."""
    lb = load_labels(); df, _wc = photo_people()
    ppc = df.groupby("cluster_id").photo_id.nunique().to_dict() if df is not None else {}
    people = {}
    for c, l in lb.items():
        if l.get("status") != "labeled": continue
        c = int(c)
        key = f"gid:{l['guest_id']}" if l.get("guest_id") is not None else f"cluster:{c}"
        if key not in people or ppc.get(c, 0) > ppc.get(people[key], 0): people[key] = c
    return sorted(set(people.values()))

def _review_thumbs(cid, my_ids, df):
    """(cover_pid, best_pid): cover = the guest's best solo/focus frame (deck-cover-like);
    best = their top-scoring frame overall (could be a group/couple shot)."""
    if df is None: return None, None
    sub = df[df.cluster_id.isin(my_ids)]
    if not len(sub): return None, None
    ranked = sub.sort_values(["score", "photo_id"], ascending=[False, True]).drop_duplicates("photo_id")
    focus = ranked[ranked.role == "focus"]
    cover = focus.iloc[0].photo_id if len(focus) else ranked.iloc[0].photo_id
    best = next((p for p in ranked.photo_id if p != cover), cover)
    return cover, best

def _review_row(cid, lb, df, tier_ov, pal_ov, nm):
    """Full review row for one guest (tier, swatches, fallback flag, thumbnails). `flags` may be
    empty — callers decide whether to keep it. Palette + fallback come straight from guest_palette."""
    import guest_palette as gp; bw = _bw(); cid = int(cid)
    my_ids = bw.union_ids(cid, lb)
    n = int(df[df.cluster_id.isin(my_ids)].photo_id.nunique()) if df is not None else 0
    tier = bw.tier_of(cid, n, tier_ov)
    bd = min(abs(n - b) for b in TIER_BOUNDARIES)
    ov = pal_ov.get(str(cid))
    if ov:                                             # human veto already recorded -> not a fallback anymore
        tok = gp.build_tokens(cid, df, my_ids, override=ov); fallback = False
    elif df is not None:
        tok = gp.build_tokens(cid, df, my_ids)         # derive from the guest's own photos
        fallback = tok["guest_accent"].lower() == gp.FALLBACK_ACCENT.lower()
    else:
        tok = dict(guest_accent=gp.FALLBACK_ACCENT, guest_support=gp.FALLBACK_SUPPORT, accent_ink=gp.INK); fallback = True
    flags = []
    if bd <= REVIEW_BAND: flags.append("boundary")     # (a) photo count near a tier cut point
    if fallback: flags.append("fallback")              # (b) accent came from the fallback path
    if tier == "light": flags.append("light")          # (c) hand-marked light stays in the queue so it can be undone
    cover, best = _review_thumbs(cid, my_ids, df)
    thumb = lambda p: (f"/api/review_thumb?pid={quote(p, safe='')}" if p else f"/api/face?cid={cid}")
    return dict(cid=cid, name=nm.get(cid) or lb.get(str(cid), {}).get("name") or f"#{cid}",
                n_photos=n, tier=tier, boundary_distance=bd, flags=flags, accent_fallback=bool(fallback),
                accent=tok["guest_accent"], support=tok["guest_support"], accent_ink=tok["accent_ink"],
                cover=thumb(cover), best_shot=thumb(best), email=lb.get(str(cid), {}).get("email", ""))

def _review_ctx():
    import guest_palette as gp; bw = _bw()
    return load_labels(), photo_people()[0], bw.load_tier_overrides(), gp.load_overrides(), name_map()

def _compute_review_rows(include_all=False):
    """Expensive pass: derive every guest's palette (parallelised — ~8s cold for ~130 guests) and
    keep only the flagged ones, sorted by risk (nearest boundary first). include_all keeps every
    labeled guest (unflagged rows have empty flags; flagged still sort first)."""
    from concurrent.futures import ThreadPoolExecutor
    lb, df, tier_ov, pal_ov, nm = _review_ctx()
    cids = _review_guest_cids()
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(lambda c: _review_row(c, lb, df, tier_ov, pal_ov, nm), cids))
    if not include_all: rows = [r for r in rows if r["flags"]]
    rows.sort(key=lambda r: (not r["flags"], r["boundary_distance"], r["name"].lower()))
    return rows

def review_rows_cached(include_all=False):
    """Base flagged rows, recomputed only when labels / tier / palette / photo_people change.
    review_state (approvals) is deliberately NOT in the signature, so the rapid approve loop
    never triggers the expensive palette recompute."""
    sig = (_mtime(LABELS), _mtime(TIER_OVERRIDE), _mtime(PALETTE_OVERRIDE), _mtime(D / "photo_people.parquet"))
    if _rev.get("sig") != sig:
        _rev["rows"] = _compute_review_rows(); _rev["all"] = None; _rev["sig"] = sig
    if include_all:
        if _rev.get("all") is None: _rev["all"] = _compute_review_rows(include_all=True)
        return _rev["all"]
    return _rev["rows"]

def review_queue_payload(include_all=False):
    base = review_rows_cached(include_all); st = load_review_state()
    rows = [dict(r, reviewed=bool(st.get(str(r["cid"]), {}).get("reviewed"))) for r in base]
    return dict(rows=rows, total=len(rows), reviewed=sum(1 for r in rows if r["reviewed"]),
                boundaries=list(TIER_BOUNDARIES), tiers=list(VALID_TIERS))

def review_row_response(cid, recompute=False):
    """One row for a POST response. approve() reuses the warm cache (instant); tier/accent writes
    pass recompute=True to reflect the just-written override without rebuilding the whole queue."""
    cid = int(cid)
    if not recompute:
        r = next((x for x in review_rows_cached() if x["cid"] == cid), None)
        if r is not None:
            st = load_review_state(); return dict(r, reviewed=bool(st.get(str(cid), {}).get("reviewed")))
    lb, df, tier_ov, pal_ov, nm = _review_ctx()
    r = _review_row(cid, lb, df, tier_ov, pal_ov, nm)
    st = load_review_state()
    return dict(r, reviewed=bool(st.get(str(cid), {}).get("reviewed")))

def review_thumb(pid, size=520):
    """Downscaled full-photo thumbnail (cached under crops/) so the queue can show ~2 photos per
    guest without shipping full-res wedding images."""
    safe = re.sub(r"[^\w.-]", "_", pid)
    out = CROPS / f"pt_{safe}_{size}.jpg"
    if not out.exists():
        src = CACHE / pid
        if not src.exists(): return None
        img = cv2.imread(str(src))
        if img is None: return None
        H, W = img.shape[:2]; sc = size / max(H, W, 1)
        if sc < 1: img = cv2.resize(img, (max(1, int(W * sc)), max(1, int(H * sc))), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return out

def _hex7(s):
    """Normalise a #rrggbb string or raise ValueError."""
    s = str(s or "").strip().lower()
    if not s.startswith("#"): s = "#" + s
    if not re.fullmatch(r"#[0-9a-f]{6}", s): raise ValueError(f"bad hex {s!r}")
    return s

class H(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def _file(self, path, ctype):
        b = Path(path).read_bytes(); self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-cache" if str(path).endswith((".html", ".json")) else "max-age=86400"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/": return self._file(APP_BUNDLE if APP_BUNDLE.exists() and (HERE / "app" / ".unified").exists() else HERE / "label_ui.html", "text/html; charset=utf-8")
        if u.path == "/people": return self._file(HERE / "people_ui.html", "text/html; charset=utf-8")
        if u.path == "/namer": return self._file(HERE / "label_ui.html", "text/html; charset=utf-8")
        if u.path == "/api/graph": return self._json(graph_json(int(q.get("min", ["50"])[0])))
        if u.path == "/api/shared":
            cids = [int(x) for x in q.get("cids", [""])[0].split(",") if x.strip()]
            if not cids: return self._json(dict(count=0, photos=[], by_event={}))
            return self._json(shared_photos(cids, q.get("event", [None])[0], int(q.get("limit", ["400"])[0])))
        if u.path == "/api/wrapped": return self._json(wrapped_list())
        if u.path == "/api/ourpicks":
            sel = json.loads((D / "our_picks.json").read_text()) if (D / "our_picks.json").exists() else []
            both = faces[faces.cluster_id.isin([15, 50])].groupby("photo_id").cluster_id.nunique()
            ids = set(both[both == 2].index)
            cand = photos[photos.photo_id.isin(ids)].copy()
            nf = faces.groupby("photo_id").face_id.count()
            cand["nf"] = cand.photo_id.map(nf)
            df, _wc2 = photo_people()
            if df is not None:
                q = df[df.cluster_id.isin([15, 50])].groupby("photo_id")["look"].mean()
                cand["q"] = cand.photo_id.map(q).fillna(0)
            else: cand["q"] = 0
            cand = cand.sort_values("q", ascending=False).head(300)
            return self._json(dict(selected=sel, candidates=[dict(photo_id=r.photo_id, url=f"/cache/{quote(r.photo_id)}",
                gallery=r.gallery, t=str(r.taken_at)[11:16], nf=int(r.nf)) for r in cand.itertuples()]))
        if u.path == "/picks": return self._file(HERE / "picks_ui.html", "text/html; charset=utf-8")
        if u.path == "/api/groups":
            g = json.loads((D / "groups.json").read_text()) if (D / "groups.json").exists() else {"groups": []}
            return self._json(dict(groups=_groups_with_together(g.get("groups", []))))
        if u.path == "/api/group_suggest":
            # rank candidates by mean over members of min(shared/|cand|, shared/|member|) — hub-resistant affinity
            gid = q.get("id", [""])[0]
            gdata = json.loads((D / "groups.json").read_text()) if (D / "groups.json").exists() else {"groups": []}
            pairs, nphotos, prim = _cooccurrence()
            if "cids" in q:   # draft mode: suggest against an arbitrary member list
                raw = [int(x) for x in q["cids"][0].split(",") if x.strip()]
                members = [prim.get(m, m) for m in raw if prim.get(m, m) not in (15, 50)]
            else:
                grp = next((x for x in gdata["groups"] if x["id"] == gid), None)
                if not grp: return self._json(dict(suggestions=[]))
                members = [prim.get(m, m) for m in grp["members"] if prim.get(m, m) not in (15, 50)]
            taken = set(members) | {15, 50}
            if not members: return self._json(dict(suggestions=[], note="add a first person to seed suggestions"))
            nm = name_map(); rows = []
            for c in set(nphotos) - taken:
                if c not in nm: continue
                scores, anchors = [], []
                for m in members:
                    t = pairs.get(tuple(sorted((c, m))), 0)
                    if t >= 2:
                        sc = min(t / nphotos[c], t / nphotos[m]); scores.append(sc); anchors.append((sc, t, m))
                    else: scores.append(0.0)
                if not any(scores): continue
                mean = sum(scores) / len(members)
                anchors.sort(key=lambda a: (-a[1], -a[0]))   # #7: `why` = top co-members by raw shared-photo count
                f = faces[faces.cluster_id == c].sort_values("det_score", ascending=False)
                face = f"/crop/{quote(f.iloc[0].face_id, safe='')}" if len(f) else ""
                rows.append(dict(cid=int(c), name=nm[c], score=round(100 * mean, 1), photos=int(nphotos[c]), face=face,
                                 why=[dict(name=nm.get(a[2], f"#{a[2]}"), together=int(a[1]), pct=round(100 * a[0], 1)) for a in anchors[:2]]))
            rows.sort(key=lambda r: -r["score"])
            return self._json(dict(suggestions=rows[:15]))
        if u.path == "/api/group_presets":
            # community detection over labeled people -> proposed groups (couple excluded, hub-resistant weights)
            import networkx as nx
            pairs, nphotos, prim = _cooccurrence()
            nm = name_map()
            gdata = json.loads((D / "groups.json").read_text()) if (D / "groups.json").exists() else {"groups": []}
            already = {m for g in gdata["groups"] for m in g["members"]}
            Gx = nx.Graph()
            for (a, b), t in pairs.items():
                if t < 3 or a in (15, 50) or b in (15, 50) or a not in nm or b not in nm: continue
                w = min(t / nphotos[a], t / nphotos[b])   # same hub-resistant affinity as suggestions
                if w >= 0.03: Gx.add_edge(a, b, weight=w)
            min_size = max(2, int(q.get("min", ["2"])[0]))
            comms = sorted(nx.community.louvain_communities(Gx, weight="weight", resolution=1.3, seed=7), key=len, reverse=True)
            BRIDE, GROOM = {110, 622, 1167}, {214, 10}
            out = []
            for c in comms:
                mem = sorted(c, key=lambda x: -nphotos.get(x, 0))
                fresh = [m for m in mem if m not in already]
                if len(mem) < max(3, min_size) or len(fresh) / len(mem) < 0.5: continue   # mostly grouped already -> skip
                side = "Preethi's side" if c & BRIDE else ("Neel's side" if c & GROOM else None)
                top = nm[mem[0]].split(" ")[0]
                label = f"{top}'s circle" + (f" ({side})" if side else "")
                tag = _group_tag(set(mem), pairs, nphotos)
                faces_ = []
                for m in mem[:24]:
                    f = faces[faces.cluster_id == m].sort_values("det_score", ascending=False)
                    faces_.append(dict(cid=int(m), name=nm[m], face=f"/crop/{quote(f.iloc[0].face_id, safe='')}" if len(f) else ""))
                out.append(dict(name=label, size=len(mem), members=[int(m) for m in mem], preview=faces_, tag=tag))
            if min_size <= 2:
                # couples pass: mutual-best pairs with strong two-way affinity — "give couples a chance"
                aff = {}
                for (a1, b1), t in pairs.items():
                    if t < 4 or a1 in (15, 50) or b1 in (15, 50) or a1 not in nm or b1 not in nm: continue
                    w = min(t / nphotos[a1], t / nphotos[b1])
                    aff.setdefault(a1, []).append((w, b1)); aff.setdefault(b1, []).append((w, a1))
                best = {c: max(v)[1] for c, v in aff.items()}
                bestw = {c: max(v)[0] for c, v in aff.items()}
                seen_pair = set()
                pairs_out = []
                for a1, b1 in best.items():
                    if best.get(b1) != a1: continue                    # must be each other's #1
                    key2 = tuple(sorted((a1, b1)))
                    if key2 in seen_pair or a1 in already or b1 in already: continue
                    seen_pair.add(key2)
                    w = min(bestw[a1], bestw[b1])
                    if w < 0.22: continue                              # both sides strongly tied
                    faces_ = []
                    for m in key2:
                        f = faces[faces.cluster_id == m].sort_values("det_score", ascending=False)
                        faces_.append(dict(cid=int(m), name=nm[m], face=f"/crop/{quote(f.iloc[0].face_id, safe='')}" if len(f) else ""))
                    pairs_out.append((w, dict(name=f"{nm[key2[0]].split(' ')[0]} & {nm[key2[1]].split(' ')[0]}", size=2,
                                              members=[int(m) for m in key2], preview=faces_,
                                              tag=f"couple / pair — each other's #1 match ({round(100*w)}% tie)")))
                pairs_out.sort(key=lambda x: -x[0])
                out.extend(pp_ for _, pp_ in pairs_out[:8])
            return self._json(dict(presets=out[:14]))
        if u.path == "/groups": return self._file(HERE / "groups_ui.html", "text/html; charset=utf-8")
        if u.path == "/explore":
            # local EDA: viewer-centered explorer over ALL labeled guests (no groups needed)
            from group_explorer import member_map_payload, render_admin_explorer
            pairs, nphotos, prim = _cooccurrence()
            nm = name_map()
            cid = int(q.get("cid", ["15"])[0]); pv = prim.get(cid, cid)
            rev = [c for c, pr in prim.items() if pr == pv]
            my_photos = sorted(set(faces[faces.cluster_id.isin(rev)].photo_id))
            sets_ = _co["sets"]; pg = photos.set_index("photo_id")
            co_counts = {}
            for pid in my_photos:
                for oc in sets_.get(pid, ()):
                    if oc != pv: co_counts[oc] = co_counts.get(oc, 0) + 1
            members_ids = [pv] + [c for c, n in sorted(co_counts.items(), key=lambda kv: -kv[1]) if n >= 2 and c in nm][:40]
            mem_info = [dict(cid=int(c), name=nm.get(c, f"#{c}"), first=(nm.get(c, f"#{c}").split(" ")[0]), face=f"/api/face?cid={c}") for c in members_ids]
            mset = set(members_ids)
            metas = []
            for pid in my_photos:
                mem = sorted(sets_.get(pid, set()) & mset) or [pv]
                if pv not in mem: mem = [pv] + mem
                pr = pg.loc[pid]
                metas.append(dict(id=pid, s=f"/cache/{quote(pid)}", l=f"/cache/{quote(pid)}",
                                  t=str(pr.taken_at)[11:16], gallery=str(pr.gallery).title(), mem=[int(x) for x in mem]))
            metas.sort(key=lambda m: (m["gallery"], m["t"]))
            edges = [[int(a1), int(b1), int(w)] for (a1, b1), w in pairs.items() if a1 in mset and b1 in mset and w >= 2]
            opts = "".join(f'<option value="{r["cluster"]}"{" selected" if int(r["cluster"]) == pv else ""}>{r["name"]} ({r["n_photos"]})</option>'
                           for r in sorted(json.loads((D / "send_manifest.json").read_text()), key=lambda x: -x["n_photos"])) if (D / "send_manifest.json").exists() else ""
            extra = f'<div style="margin-bottom:10px"><select onchange="location=\'/explore?cid=\'+this.value" style="font:inherit;padding:6px 10px;border-radius:8px;background:#24151a;color:#f7efe6;border:1px solid rgba(255,255,255,.15)">{opts}</select> <span style="color:#c9b3a6;font-size:12px">LOCAL EDA — all co-stars, no quality filter, never deployed</span></div>'
            payload = member_map_payload(f"{nm.get(pv, '#'+str(pv))} — everyone", int(pv), mem_info, metas, edges)
            html = render_admin_explorer(payload, "/guests", header_extra=extra)
            b = html.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
        if u.path == "/guests":   # LOCAL admin index of every guest deck — never deployed (lives on :8792 only)
            mf = D / "send_manifest.json"
            rows = json.loads(mf.read_text()) if mf.exists() else []
            live = "https://photos.preethiandneel.com"
            body = "".join(f"""<tr><td><img loading=lazy src='/api/face?cid={r["cluster"]}'></td><td>{r["name"]}</td><td>#{r["cluster"]}</td>
<td>{r["n_photos"]}</td><td>{r.get("n_picks","")}</td><td>{r.get("email","") or "<i>no email</i>"}</td>
<td><a href='http://localhost:8798/{r["token"]}/' target=_blank>local</a></td><td><a href='{live}/{r["token"]}/' target=_blank>live</a></td>
<td><a href='/highlights?cid={r["cluster"]}' target=_blank>bar</a></td><td><a href='/?cid={r["cluster"]}#/admin?cid={r["cluster"]}' target=_blank>admin</a></td></tr>""" for r in rows)
            html = f"""<!doctype html><meta charset=utf-8><title>Guest decks — admin</title>
<style>body{{font:14px system-ui;margin:20px;background:#f6f4ef;color:#1a1a19}}h1{{font-size:18px}}input{{font:inherit;padding:6px 10px;border:1px solid #e4e1d8;border-radius:8px;min-width:240px}}
table{{border-collapse:collapse;background:#fff;width:100%;margin-top:12px}}th,td{{padding:6px 10px;border-bottom:1px solid #e4e1d8;text-align:left}}th{{font-size:12px;color:#6b6963;text-transform:uppercase;letter-spacing:.05em}}
td img{{width:36px;height:36px;border-radius:50%;object-fit:cover;display:block}}a{{color:#b8862b}}</style>
<h1>Guest decks ({len(rows)}) — LOCAL TESTING ONLY</h1><input id=q placeholder="filter name/email…" oninput="f()">
<p style='color:#6b6963;font-size:13px'>local = http://localhost:8798 preview of site_guest/ · live = what's currently on Cloudflare (may be older than local)</p>
<table><thead><tr><th></th><th>Name</th><th>#</th><th>Photos</th><th>Picks</th><th>Email</th><th>Local</th><th>Live</th><th>Bar</th><th>Admin</th></tr></thead><tbody id=tb>{body}</tbody></table>
<script>function f(){{const q=document.getElementById('q').value.toLowerCase();document.querySelectorAll('#tb tr').forEach(tr=>tr.style.display=tr.textContent.toLowerCase().includes(q)?'':'none')}}</script>"""
            b = html.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
        if u.path == "/api/highlights":
            df, wc = photo_people()
            if df is None: return self._json(dict(error="photo_people.py has not finished yet"), 503)
            nm = name_map()
            if "cid" not in q:   # index: everyone with >=5 photos
                pp = df.groupby("cluster_id").photo_id.nunique()
                return self._json([dict(cid=int(c), name=nm.get(int(c)), n_photos=int(n), thr=thr_of(int(c))[0], auto=thr_of(int(c))[1])
                                   for c, n in pp.items() if n >= 5 and int(c) not in exclude])
            cid = int(q["cid"][0])
            stored, is_auto = thr_of(cid)
            thr = float(q["thr"][0]) if "thr" in q else stored
            picks, meta = pick_highlights(cid, df, wc, thr)
            picks = [dict(p, url=f"/cache/{quote(p['photo_id'])}", people=breakdown(p["photo_id"], df, nm)) for p in picks]
            return self._json(dict(cid=cid, name=nm.get(cid), thr=thr, stored_thr=stored, auto=is_auto, picks=picks, **meta))
        if u.path == "/api/photo_people":
            df, hl = photo_people(); pid = unquote(q.get("photo_id", [""])[0]).replace("/cache/", "")
            if df is None: return self._json(dict(error="not ready"), 503)
            return self._json(dict(photo_id=pid, people=breakdown(pid, df, name_map())))
        if u.path == "/highlights": return self._file(HERE / "highlights_ui.html", "text/html; charset=utf-8")
        if u.path == "/api/photo":   # faces in one photo (any size/confidence), with names + cluster ids — for right-click naming in lightboxes
            pid = unquote(q.get("photo_id", [""])[0]).replace("/site/img/l/", "").replace("/site/img/s/", "").replace("../img/l/", "").replace("../img/s/", "").replace("/cache/", "")
            allf = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
            ff = allf[allf.photo_id == pid]; ph = photos[photos.photo_id == pid]
            if ph.empty: return self._json(dict(photo_id=pid, faces=[]), 404)
            nm = name_map(); lb = load_labels(); r = ph.iloc[0]
            return self._json(dict(photo_id=pid, w=int(r.w), h=int(r.h), gallery=r.gallery, url=f"/cache/{quote(pid)}",
                                   faces=[dict(cid=int(f.cluster_id), name=nm.get(int(f.cluster_id)), status=lb.get(str(int(f.cluster_id)), {}).get("status"),
                                              photos=int(stats.loc[int(f.cluster_id), "photos"]) if int(f.cluster_id) in stats.index else 1,
                                              box=[round(f.x1), round(f.y1), round(f.x2), round(f.y2)], det=round(float(f.det_score), 2)) for f in ff.itertuples()]))
        if u.path == "/api/names": return self._json({str(k): v for k, v in name_map().items()})
        if u.path == "/api/review_queue": return self._json(review_queue_payload(include_all=q.get("all", ["0"])[0] in ("1", "true")))
        if u.path == "/api/review_thumb":
            pid = unquote(q.get("pid", [""])[0]).replace("/cache/", "")
            p = review_thumb(pid)
            if p is None: return self.send_error(404)
            return self._file(p, "image/jpeg")
        if u.path.startswith("/site/"):
            fp = SITE / unquote(u.path[6:])
            if fp.is_dir(): fp = fp / "index.html"
            if not fp.exists(): return self.send_error(404)
            ct = {"json": "application/json", "html": "text/html; charset=utf-8", "jpg": "image/jpeg", "png": "image/png", "css": "text/css", "js": "application/javascript"}.get(fp.suffix[1:], "application/octet-stream")
            return self._file(fp, ct)
        if u.path.startswith("/app") or u.path == "/admin" or u.path.startswith("/wrapped") or u.path.startswith("/shared") or u.path.startswith("/graph"):
            if APP_BUNDLE.exists(): return self._file(APP_BUNDLE, "text/html; charset=utf-8")
        if u.path == "/api/export.csv":
            b = labels_csv().encode(); self.send_response(200); self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=labels.csv"); self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
        if u.path == "/api/history":
            rows = [json.loads(x) for x in HIST.read_text().splitlines()[-200:]] if HIST.exists() else []; return self._json(rows[::-1])
        if u.path == "/api/people":
            lb = load_labels(); rows = []
            for c in queue:
                l = lb.get(str(c), {}); ev = faces[faces.cluster_id == c].groupby("gallery").photo_id.nunique().to_dict()
                f = faces[faces.cluster_id == c].sort_values("det_score", ascending=False).iloc[0]
                rows.append(dict(cid=c, photos=int(stats.loc[c, "photos"]), events=ev, face=f"/crop/{quote(f.face_id, safe='')}", label=l))
            return self._json(dict(rows=rows, guests=guests))
        if u.path == "/review":
            lb = load_labels(); rows = []
            for cid, l in sorted(lb.items(), key=lambda kv: -int(stats.loc[int(kv[0]), "photos"]) if int(kv[0]) in stats.index else 0):
                c = int(cid); mine = faces[faces.cluster_id == c].sort_values("det_score", ascending=False).drop_duplicates("photo_id").head(10)
                imgs = "".join(f'<img src="/crop/{quote(r.face_id, safe="")}">' for r in mine.itertuples())
                tag = {"not_guest": "not a guest", "merged": f"merged into #{l.get('merge_into')}"}.get(l.get("status"), l.get("name", "?") + (" · provisional" if l.get("provisional") else ""))
                n = int(stats.loc[c, "photos"]) if c in stats.index else 0
                rows.append(f'<a class=r href="/?cid={c}"><div class=h><b>#{c}</b> <span>{tag}</span><small>{n} photos{" · " + l["email"] if l.get("email") else ""}</small></div><div class=f>{imgs}</div></a>')
            html = f"""<!doctype html><meta charset=utf-8><title>Review names</title><style>body{{font:14px system-ui;margin:20px;background:#f6f4ef;color:#1a1a19}}h1{{font-size:18px}}.r{{display:block;color:inherit;text-decoration:none;background:#fff;border:1px solid #e4e1d8;border-radius:10px;padding:10px 12px;margin:0 0 10px;cursor:pointer}}.r:hover{{border-color:#b8862b}}.h{{display:flex;gap:12px;align-items:baseline}}.h span{{font-size:16px;font-weight:600}}.h small{{color:#6b6963}}.f{{display:flex;gap:4px;margin-top:8px;flex-wrap:wrap}}.f img{{width:64px;height:64px;border-radius:6px;object-fit:cover}}a{{color:#b8862b;text-decoration:none}}</style>
<h1>Named clusters ({len(rows)}) — click a card to open it in the namer</h1>{"".join(rows)}"""
            b = html.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
        if u.path == "/api/state":
            lb = load_labels(); return self._json(dict(queue=queue, guests=guests, labels=lb, min=a.min,
                                                     photos={int(c): int(stats.loc[c, "photos"]) for c in queue}))
        if u.path == "/api/cluster": return self._json(cluster_payload(int(q["cid"][0])))
        if u.path == "/api/face":
            c = int(q["cid"][0]); f = faces[faces.cluster_id == c].sort_values("det_score", ascending=False).iloc[0]
            return self._file(crop(f.face_id, 72), "image/jpeg")
        if u.path.startswith("/crop/"): return self._file(crop(unquote(u.path[6:])), "image/jpeg")
        if u.path.startswith("/cache/"): return self._file(CACHE / unquote(u.path[7:]), "image/jpeg")
        self.send_error(404)
    def do_POST(self):
        u = urlparse(self.path); n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        if u.path == "/api/label":
            with lock:
                cid = body.pop("cid"); new = None if body.get("clear") else body
                set_label(cid, new)
            return self._json(dict(ok=True))
        if u.path == "/api/threshold":
            with lock:
                th = thresholds(); cid = str(body["cid"])
                if body.get("auto"):
                    df, _ = photo_people(); g = df[(df.cluster_id == int(cid)) & (df.blink == 0) & (df.edge == 0)]
                    if len(g) == 0: g = df[df.cluster_id == int(cid)]
                    k = min(len(g), max(30, BUDGET_HL))
                    auto = round(min(float(np.sort(g.score.values)[::-1][k - 1]), float(np.percentile(g.score.values, 55))), 1)
                    th[cid] = dict(value=auto, auto=True)
                else:
                    th[cid] = dict(value=round(float(body["value"]), 1), auto=False)
                tmp = THRESH.with_suffix(".tmp"); tmp.write_text(json.dumps(th)); tmp.replace(THRESH)
            return self._json(dict(ok=True, **th[cid]))
        if u.path == "/api/groups":
            with lock:
                gf = D / "groups.json"
                g = json.loads(gf.read_text()) if gf.exists() else {"groups": []}
                op = body.get("op"); import uuid
                if op == "create": g["groups"].append(dict(id=uuid.uuid4().hex[:8], name=body["name"].strip(), members=[]))
                elif op == "rename":
                    for x in g["groups"]:
                        if x["id"] == body["id"]: x["name"] = body["name"].strip()
                elif op == "delete": g["groups"] = [x for x in g["groups"] if x["id"] != body["id"]]
                elif op == "add":
                    for x in g["groups"]:
                        if x["id"] == body["id"]: x["members"] = sorted(set(x["members"]) | set(int(c) for c in body["cids"]))
                elif op == "remove":
                    for x in g["groups"]:
                        if x["id"] == body["id"]: x["members"] = [m for m in x["members"] if m not in set(int(c) for c in body["cids"])]
                tmp = gf.with_suffix(".tmp"); tmp.write_text(json.dumps(g, indent=1, ensure_ascii=False)); tmp.replace(gf)
            return self._json(dict(ok=True, groups=_groups_with_together(g["groups"])))
        if u.path == "/api/ourpicks":
            with lock:
                sel = [str(x) for x in body.get("photo_ids", [])][:16]
                tmp = (D / "our_picks.json").with_suffix(".tmp"); tmp.write_text(json.dumps(sel)); tmp.replace(D / "our_picks.json")
            return self._json(dict(ok=True, n=len(sel)))
        if u.path == "/api/undo":
            with lock:
                lines = HIST.read_text().splitlines() if HIST.exists() else []
                if not lines: return self._json(dict(ok=False, msg="nothing to undo"))
                last = json.loads(lines[-1]); lb = load_labels()
                if last["before"] is None: lb.pop(str(last["cid"]), None)
                else: lb[str(last["cid"])] = last["before"]
                save_labels(lb); HIST.write_text("\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""))
                log_change(last["cid"], last["after"], last["before"], who="undo")
            return self._json(dict(ok=True, cid=last["cid"], restored=last["before"]))
        if u.path == "/api/import":   # CSV text in body["csv"]; columns as exported; blank name+status = clear
            n = 0
            with lock:
                for r in csv.DictReader(io.StringIO(body["csv"])):
                    cid = r["cluster_id"].strip()
                    if not cid: continue
                    st = r.get("status", "").strip()
                    if not st and not r.get("name", "").strip(): set_label(cid, None); n += 1; continue
                    g = next((x for x in guests if str(x["id"]) == r.get("guest_id", "").strip()), None) if r.get("guest_id", "").strip() else None
                    if not g and r.get("name", "").strip(): g = next((x for x in guests if x["name"].lower() == r["name"].strip().lower()), None)
                    if st == "not_guest": new = dict(status="not_guest")
                    elif st == "merged": new = dict(status="merged", merge_into=int(r["merge_into"]))
                    elif g: new = dict(status="labeled", name=g["name"], first=g["first"], last=g["last"], email=g["email"], party=g["party"], guest_id=g["id"])
                    else: new = dict(status="labeled", name=r["name"].strip(), first=r.get("first", ""), last=r.get("last", ""), email=r.get("email", ""), party=r.get("party", ""))
                    set_label(cid, new); n += 1
            return self._json(dict(ok=True, n=n))
        if u.path == "/api/review":   # pre-send review queue actions (issue #33)
            op = body.get("op")
            try: cid = int(body["cid"])
            except (KeyError, TypeError, ValueError): return self._json(dict(ok=False, error="missing/invalid cid"), 400)
            with lock:
                if op in ("approve", "unapprove"):
                    st = load_review_state()
                    if op == "approve": st[str(cid)] = dict(reviewed=True, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
                    else: st.pop(str(cid), None)
                    save_review_state(st)
                    return self._json(dict(ok=True, row=review_row_response(cid)))
                if op == "override_tier":   # write data/tier_override.json (consumed by build_wrapped)
                    tier = body.get("tier")
                    if tier not in VALID_TIERS: return self._json(dict(ok=False, error=f"bad tier {tier!r}"), 400)
                    ov = json.loads(TIER_OVERRIDE.read_text()) if TIER_OVERRIDE.exists() else {}
                    ov[str(cid)] = tier
                    tmp = TIER_OVERRIDE.with_suffix(".tmp"); tmp.write_text(json.dumps(ov, indent=1, ensure_ascii=False)); tmp.replace(TIER_OVERRIDE)
                    return self._json(dict(ok=True, row=review_row_response(cid, recompute=True)))
                if op == "swap_accent":     # write data/palette_override.json (consumed by guest_palette)
                    import guest_palette as gp
                    try:
                        accent = _hex7(body.get("accent") or gp.FALLBACK_ACCENT)
                        support = _hex7(body.get("support") or gp.FALLBACK_SUPPORT)
                    except ValueError as e:
                        return self._json(dict(ok=False, error=str(e)), 400)
                    ink, cc = gp._ink_for(accent)   # DESIGN.md pick-by-contrast rule; reject a low-contrast accent up front
                    if cc < gp.MIN_CONTRAST:
                        return self._json(dict(ok=False, error=f"accent {accent} fails contrast ({cc:.2f}:1 < {gp.MIN_CONTRAST}:1)"), 400)
                    po = json.loads(PALETTE_OVERRIDE.read_text()) if PALETTE_OVERRIDE.exists() else {}
                    po[str(cid)] = dict(accent=accent, support=support, ink=ink.lower())
                    tmp = PALETTE_OVERRIDE.with_suffix(".tmp"); tmp.write_text(json.dumps(po, indent=1, ensure_ascii=False)); tmp.replace(PALETTE_OVERRIDE)
                    return self._json(dict(ok=True, row=review_row_response(cid, recompute=True)))
            return self._json(dict(ok=False, error=f"unknown op {op!r}"), 400)
        self.send_error(404)

if __name__ == "__main__":
    print(f"{len(queue)} clusters ≥{a.min} photos to name · {len(guests)} guests · http://localhost:{a.port}")
    ThreadingHTTPServer(("0.0.0.0", a.port), H).serve_forever()
