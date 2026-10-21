"""
Shared curation logic: per-person highlight picks from photo_people.parquet + thresholds.json.
Used by label_server.py (/api/highlights) and build_wrapped.py --curated. Single source of truth
for the couple's cluster ids and the pick budget.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).parent / "data"
THRESH = D / "thresholds.json"
BUDGET_HL = 40          # max curated picks per person
MIN_PICKS = 15          # floor: thin decks fill with best-available shots (any role, no blinks)
COUPLE = {15, 50}       # Neel, Preethi cluster ids

def load_photo_people(data_dir=None):
    """Returns (df, with_couple_map). df = one row per usable face with score/role/scene."""
    d = Path(data_dir) if data_dir else D
    df = pd.read_parquet(d / "photo_people.parquet")
    wc = df[df.cluster_id.isin(COUPLE)].groupby("photo_id").cluster_id.apply(set).to_dict()
    return df, wc

def thresholds():
    return json.loads(THRESH.read_text()) if THRESH.exists() else {}

def thr_of(cid):
    t = thresholds().get(str(cid)); return (t["value"], t.get("auto", True)) if t else (0.0, True)

GRADE_MEDIUM_BAND = 15   # score within this much below someone's bar = "medium"; further = "bad"

def _bars():
    return {int(k): float(v["value"]) for k, v in thresholds().items()}

def courtesy_adjust(ok, df, cid):
    """Demote photos where another (prominent) person grades 'bad' vs their own bar —
    A gets their good photos, but B-at-their-worst is rationed everywhere."""
    import numpy as _np
    if not len(ok): return ok
    bars = _bars()
    others = df[df.photo_id.isin(ok.photo_id) & (df.cluster_id != cid) & (df.prom >= 0.4) & (df["size"] >= 48)].copy()
    if len(others):
        others["margin"] = others.score - others.cluster_id.map(bars).fillna(others.score)
        worst = others.groupby("photo_id").margin.min()
        ok = ok.copy(); ok["worst_other"] = ok.photo_id.map(worst)
        ok["look"] = ok.look - _np.where(ok.worst_other < -GRADE_MEDIUM_BAND, 0.25,
                                _np.where(ok.worst_other < 0, 0.08, 0.0))
        ok = ok.sort_values("look", ascending=False)
    return ok

def pick_highlights(cid, df, wc, thr):
    """~BUDGET_HL picks for one cluster: buckets with_couple(5|6) / focus(12+fill) / group(8),
    one per scene, score >= thr, blink/edge/background excluded, courtesy-adjusted for others."""
    m = df[df.cluster_id == cid]
    cand = m[(m.role != "background") & (m.blink == 0) & (m.edge == 0)]
    ok = courtesy_adjust(cand[cand.score >= thr].sort_values("look", ascending=False), df, cid)
    pick, used = [], set()
    def take(sub, n, tag):
        got = sum(1 for x in pick if x["bucket"] == tag)
        for r in sub.itertuples():
            if got >= n: break
            if r.scene in used: continue
            used.add(r.scene); got += 1
            pick.append(dict(photo_id=r.photo_id, bucket=tag, role=r.role, score=float(r.score), prom=round(float(r.prom), 2),
                             n_faces=int(r.n_faces), gallery=r.gallery, t=str(r.t)[:16]))
    if cid in COUPLE:
        other = (COUPLE - {cid}).pop()
        take(ok[ok.photo_id.map(lambda p: other in wc.get(p, set()))], 10, "with_couple")
    else:
        take(ok[ok.photo_id.map(lambda p: bool(wc.get(p)))], 5, "with_couple")
    take(ok[ok.role == "focus"], 20, "focus"); take(ok[ok.role == "group"], 12, "group")
    # extra genuinely-good with-couple shots beyond the cap → last section ("more")
    if cid in COUPLE:
        other = (COUPLE - {cid}).pop()
        take(ok[ok.photo_id.map(lambda p: other in wc.get(p, set()))], 5, "more")
    else:
        take(ok[ok.photo_id.map(lambda p: bool(wc.get(p)))], 5, "more")
    if len(pick) < BUDGET_HL: take(ok[ok.role == "focus"], 999, "focus")
    if len(pick) < MIN_PICKS:
        # thin deck: fill with the person's best remaining shots (no blinks/edges), any role,
        # ranked by how visible they are * how good they look — never leave a guest with 1 photo
        rest = m[(m.blink == 0) & (m.edge == 0) & ~m.scene.isin(used)].copy()
        rest = rest.sort_values(by="look", ascending=False).assign(_v=lambda d: d.prom * d.look).sort_values("_v", ascending=False)
        for r in rest.itertuples():
            if len(pick) >= MIN_PICKS: break
            if r.scene in used: continue
            used.add(r.scene)
            pick.append(dict(photo_id=r.photo_id, bucket="more", role=r.role,
                             score=float(r.score), prom=round(float(r.prom), 2), n_faces=int(r.n_faces), gallery=r.gallery, t=str(r.t)[:16]))
    pick = pick[:BUDGET_HL]; pick.sort(key=lambda x: x["t"])
    hist = np.histogram(cand.score.values, bins=20, range=(0, 100))[0].tolist() if len(cand) else [0] * 20
    return pick, dict(n_photos=int(m.photo_id.nunique()), n_cand=int(cand.photo_id.nunique()), n_pass=int(ok.photo_id.nunique()),
                      roles={k: int(v) for k, v in m.role.value_counts().items()}, hist=hist)
