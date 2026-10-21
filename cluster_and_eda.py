"""
Step 2: cluster faces into people, then produce the 80/20 EDA.

Usage: python cluster_and_eda.py [--thresh 0.55]   (reads cache/ + data/ written by extract_faces.py)

Outputs (data/):
  clusters.parquet          face_id -> cluster_id
  people_stats.csv          one row per cluster: photos, galleries, first/last seen, tier
  eda_report.html           distribution + contact sheet per cluster (open in browser, eyeball purity)
  contact/<cluster>.jpg     face-crop grids
"""
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd, cv2
from sklearn.cluster import AgglomerativeClustering

ap = argparse.ArgumentParser()
ap.add_argument("--thresh", type=float, default=0.55, help="cosine distance cut (lower = stricter)")
ap.add_argument("--min-det", type=float, default=0.65); ap.add_argument("--min-size", type=float, default=36)
ap.add_argument("--top", type=int, default=120, help="contact sheets for top-N clusters")
a = ap.parse_args()
ROOT = Path(__file__).parent / "cache"; D = Path(__file__).parent / "data"; C = D / "contact"; C.mkdir(parents=True, exist_ok=True)

faces = pd.read_parquet(D / "faces.parquet"); photos = pd.read_parquet(D / "photos.parquet")
n_all = len(faces)
faces = faces[(faces.det_score >= a.min_det) & (faces["size"] >= a.min_size)].reset_index(drop=True)
print(f"{n_all} faces detected → {len(faces)} usable after quality filter; {len(photos)} photos")

X = np.stack(faces.emb.values).astype(np.float32); X /= np.linalg.norm(X, axis=1, keepdims=True)
cl = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average", distance_threshold=a.thresh).fit(X)
faces["cluster_id"] = cl.labels_
faces[["face_id", "photo_id", "cluster_id"]].to_parquet(D / "clusters.parquet", index=False)

# ---- per-person stats -------------------------------------------------------
faces = faces.merge(photos[["photo_id", "taken_at"]], on="photo_id", how="left")
g = faces.groupby("cluster_id")
stats = pd.DataFrame({
    "faces": g.size(),
    "photos": g.photo_id.nunique(),
    "galleries": g.gallery.nunique(),
    "gallery_list": g.gallery.agg(lambda s: ", ".join(sorted(set(s)))),
    "first_seen": g.taken_at.min(), "last_seen": g.taken_at.max(),
    "avg_face_px": g["size"].mean().round(0),
    "avg_det": g.det_score.mean().round(3),
}).sort_values("photos", ascending=False)
def tier(n):
    return "A: full deck (≥15)" if n >= 15 else "B: light deck (5–14)" if n >= 5 else "C: household/thank-you (<5)"
stats["tier"] = stats.photos.map(tier)
stats.to_csv(D / "people_stats.csv")

# ---- 80/20 summary ------------------------------------------------------------
tot = stats.photos.sum()
stats["cum_share"] = stats.photos.cumsum() / tot
k80 = int((stats.cum_share < 0.8).sum()) + 1
print("\n=== 80/20 ===")
print(f"clusters (≈people): {len(stats)}   singletons: {(stats.photos==1).sum()}")
print(f"{k80} clusters account for 80% of all face-appearances ({k80/len(stats):.0%} of clusters)")
print(stats.tier.value_counts().sort_index().to_string())
print("\nTop 25:\n", stats.head(25)[["photos", "galleries", "gallery_list", "avg_face_px"]].to_string())

# ---- per-event breakdown ------------------------------------------------------
ev_rows = []
for ev, sub in faces.groupby("gallery"):
    pp = sub.groupby("cluster_id").photo_id.nunique().sort_values(ascending=False)
    n_photos = photos[photos.gallery == ev].shape[0]
    cum = pp.cumsum() / pp.sum(); k80e = int((cum < 0.8).sum()) + 1
    ev_rows.append(dict(event=ev, photos=n_photos, faces=len(sub), people=len(pp),
                        people_ge15=int((pp >= 15).sum()), people_5_14=int(((pp >= 5) & (pp < 15)).sum()), people_lt5=int((pp < 5).sum()),
                        k80=k80e, top5=", ".join(f"#{c}:{n}" for c, n in pp.head(5).items())))
ev_df = pd.DataFrame(ev_rows).sort_values("photos", ascending=False)
ev_df.to_csv(D / "event_stats.csv", index=False)
print("\n=== By event ===\n", ev_df.to_string(index=False))
# cross-event: how many people show up at 1,2,3+ events
print("\nPeople by # events attended:\n", stats.galleries.value_counts().sort_index().to_string())
# per-event × cluster matrix for the top clusters (who is where)
mat = faces.groupby(["cluster_id", "gallery"]).photo_id.nunique().unstack(fill_value=0).loc[stats.index[:60]]
mat.to_csv(D / "people_by_event.csv")

# ---- contact sheets ------------------------------------------------------------
def crop(row, pad=0.35):
    img = cv2.imread(str(ROOT / row.photo_id))
    if img is None: return None
    h, w = img.shape[:2]; bw, bh = row.x2-row.x1, row.y2-row.y1
    x1, y1 = int(max(0, row.x1-pad*bw)), int(max(0, row.y1-pad*bh)); x2, y2 = int(min(w, row.x2+pad*bw)), int(min(h, row.y2+pad*bh))
    return cv2.resize(img[y1:y2, x1:x2], (112, 112))

for cid in stats.index[: a.top]:
    sub = faces[faces.cluster_id == cid].sort_values("det_score", ascending=False).head(24)
    tiles = [t for t in (crop(r) for r in sub.itertuples()) if t is not None]
    if not tiles: continue
    while len(tiles) % 6: tiles.append(np.zeros((112, 112, 3), np.uint8))
    rows = [np.hstack(tiles[i:i+6]) for i in range(0, len(tiles), 6)]
    cv2.imwrite(str(C / f"{cid}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])

# ---- html report ---------------------------------------------------------------
import json
_lb = json.loads((D / "labels.json").read_text()) if (D / "labels.json").exists() else {}
def _nm(cid):
    l = _lb.get(str(cid), {})
    if l.get("status") == "not_guest": return "not a guest"
    if l.get("status") == "merged": return f"→ merged into #{l.get('merge_into')}"
    return l.get("name") or ""
hist = stats.photos.clip(upper=60).value_counts().sort_index()
bars = "".join(f"<div title='{n} photos: {c} people' style='display:inline-block;width:8px;margin-right:1px;background:#c96;height:{min(200, c*4)}px;vertical-align:bottom'></div>" for n, c in hist.items())
cards = "".join(
    f"<div class=c><a href='http://localhost:8792/?cid={cid}' title='open in the namer'><img src='contact/{cid}.jpg'></a><div><b>#{cid}</b> {('<span style=color:#1b8f5a>' + _nm(cid) + '</span>') if _nm(cid) else ''} — {r.photos} photos · {r.galleries} events<br><small>{r.gallery_list}</small><br><i>{r.tier}</i></div></div>"
    for cid, r in stats.head(a.top).iterrows() if (C / f"{cid}.jpg").exists())
(D / "eda_report.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Wedding Wrapped — face EDA</title>
<style>body{{font:14px system-ui;margin:24px;max-width:1200px}} .c{{display:flex;gap:12px;margin:10px 0;border-bottom:1px solid #eee;padding-bottom:8px}} .c img{{width:336px}} th,td{{padding:2px 8px;text-align:left}}</style>
<h1>Face EDA — {len(photos)} photos, {n_all} faces ({len(faces)} usable), {len(stats)} clusters @ thresh {a.thresh}</h1>
<p><b>{k80} clusters = 80% of appearances.</b> Tiers: {stats.tier.value_counts().sort_index().to_dict()}</p>
<h2>By event</h2>{ev_df.to_html(index=False)}
<h2>Top 60 people × event (photo counts)</h2><div style='overflow-x:auto'>{mat.to_html()}</div>
<h2>Photos-per-person distribution (x = photos, capped 60; y = # people)</h2><div style='height:200px'>{bars}</div>
<h2>Top {a.top} clusters — check purity: is every tile the same person?</h2>{cards}""")
print(f"\nreport → {D/'eda_report.html'}")
