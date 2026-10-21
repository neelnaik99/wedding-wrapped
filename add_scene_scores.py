"""Add 0-100 score + per-person scene ids to photo_people.parquet; fit per-person auto thresholds → data/thresholds.json"""
import json
import numpy as np, pandas as pd
from pathlib import Path
D = Path("data"); BUDGET = 25
df = pd.read_parquet(D / "photo_people.parquet")
df["score"] = (100 * df.look.rank(pct=True)).round(1)          # global 0-100 scale, comparable across people
df["t"] = pd.to_datetime(df["t"])
# per-person scenes (same rule as everywhere: ≤120s gap + people-overlap ≥0.34)
ppl = df[df["size"] >= 60].groupby("photo_id").cluster_id.apply(frozenset)
scenes = np.empty(len(df), dtype=np.int32); df = df.sort_values(["cluster_id", "t"]).reset_index(drop=True)
cur = -1; last = None
for i, r in enumerate(df.itertuples()):
    A = ppl.get(r.photo_id, frozenset()); B = ppl.get(last.photo_id, frozenset()) if last is not None and last.cluster_id == r.cluster_id else frozenset()
    new = last is None or r.cluster_id != last.cluster_id or r.gallery != last.gallery or (r.t - last.t).total_seconds() > 120 or len(A & B) / max(1, len(A | B)) < 0.34
    cur += int(new); scenes[i] = cur; last = r
df["scene"] = scenes
df.to_parquet(D / "photo_people.parquet", index=False)
# auto threshold per person: keep their best K in play (K = min(n, max(30, BUDGET))) but never above their 55th pct
TH = D / "thresholds.json"; existing = json.loads(TH.read_text()) if TH.exists() else {}
out = dict(existing)
for cid, g in df.groupby("cluster_id"):
    g2 = g[(g.blink == 0) & (g.edge == 0)]
    if len(g2) == 0: g2 = g
    n = len(g2); k = min(n, max(50, 2 * BUDGET))
    kth = float(np.sort(g2.score.values)[::-1][k - 1]); p55 = float(np.percentile(g2.score.values, 45))
    auto = round(min(kth, p55), 1)
    prev = existing.get(str(int(cid)))
    if prev and not prev.get("auto", True): out[str(int(cid))] = prev                      # keep user-set values
    else: out[str(int(cid))] = dict(value=auto, auto=True)
TH.write_text(json.dumps(out))
print(len(df), "rows; thresholds for", len(out), "people; sample:", {k: out[k] for k in list(out)[:3]})
