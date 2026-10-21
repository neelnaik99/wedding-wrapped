"""
Per-photo, per-person breakdown for EVERY usable face, then highlights for everyone.

For each face (photo × person):
  look     how good a shot of *them* it is: face sharpness, detector confidence, eyes-open, smile (landmarks), edge/blink penalties
  role     focus      — ≤4 faces and theirs is ≥60% of the largest (or a 2-shot ≥45%)
           group      — ≥5 faces and theirs is ≥55% of the largest (an equal participant in a group photo)
           background — everything else (small/peripheral)
  prom     face size / largest face in the photo
Highlights per person = focus/group rows that look good, one per moment, buckets: focus · with the couple · group (≤ BUDGET total)

Outputs: data/photo_people.parquet, data/highlights.json   (rerun is incremental for landmarks via data/face_expr.json)
"""
import json, math, time
from pathlib import Path
import numpy as np, pandas as pd, cv2
from tqdm import tqdm

HERE = Path(__file__).parent; D, CACHE = HERE / "data", HERE / "cache"
BUDGET, COUPLE = 25, {15, 50}
faces = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
faces = faces[(faces.det_score >= .65) & (faces["size"] >= 36)].copy()
photos = pd.read_parquet(D / "photos.parquet").merge(pd.read_parquet(D / "photo_features.parquet"), on="photo_id")
photos["t"] = pd.to_datetime(photos.taken_at, format="%Y:%m:%d %H:%M:%S", errors="coerce")
faces = faces.merge(photos[["photo_id", "w", "h", "sharpness", "t"]], on="photo_id")
exclude = set(json.loads((D / "exclude.json").read_text())) if (D / "exclude.json").exists() else set()
print(f"{len(faces)} usable faces in {faces.photo_id.nunique()} photos")

# ---- role in the photo ---------------------------------------------------------------------
g = faces.groupby("photo_id")["size"]
faces["max_face"] = g.transform("max"); faces["n_faces"] = g.transform("count"); faces["prom"] = faces["size"] / faces.max_face
def role(r):
    if r.n_faces <= 4: return "focus" if (r.prom >= 0.6 or (r.n_faces == 2 and r.prom >= 0.45) or r.n_faces == 1) else "background"
    return "group" if r.prom >= 0.55 else "background"
faces["role"] = [role(r) for r in faces.itertuples()]
faces["edge"] = ((faces.x1 < 8) | (faces.y1 < 8) | (faces.x2 > faces.w - 8) | (faces.y2 > faces.h - 8)).astype(int)

# ---- face sharpness (all) + landmarks (faces ≥48px, cached) --------------------------------------
EXPR = D / "face_expr.json"; cache = json.loads(EXPR.read_text()) if EXPR.exists() else {}
from insightface.app import FaceAnalysis
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"], allowed_modules=["detection", "landmark_2d_106"]); app.prepare(ctx_id=0, det_size=(320, 320))
sharp, eye, smile = {}, {}, {}
t0 = time.time(); cur_pid, img, gray = None, None, None
for r in tqdm(faces.sort_values("photo_id").itertuples(), total=len(faces), mininterval=10):
    if r.photo_id != cur_pid:
        img = cv2.imread(str(CACHE / r.photo_id)); gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); cur_pid = r.photo_id
        if len(sharp) % 2000 == 0: EXPR.write_text(json.dumps(cache))
    H, W = gray.shape[:2]; x1, y1, x2, y2 = int(max(0, r.x1)), int(max(0, r.y1)), int(min(W, r.x2)), int(min(H, r.y2))
    c = gray[y1:y2, x1:x2]; sharp[r.face_id] = float(cv2.Laplacian(cv2.resize(c, (128, 128)), cv2.CV_64F).var()) if c.size > 100 else 0.0
    if r.face_id in cache: eye[r.face_id], smile[r.face_id] = cache[r.face_id]; continue
    if r.size < 48: continue
    bw, bh = r.x2 - r.x1, r.y2 - r.y1; cx1, cy1, cx2, cy2 = int(max(0, r.x1 - bw)), int(max(0, r.y1 - bh)), int(min(W, r.x2 + bw)), int(min(H, r.y2 + bh))
    fs = app.get(img[cy1:cy2, cx1:cx2])
    if not fs: cache[r.face_id] = [None, None]; continue
    ccx, ccy = (cx2 - cx1) / 2, (cy2 - cy1) / 2; f = min(fs, key=lambda f: abs((f.bbox[0] + f.bbox[2]) / 2 - ccx) + abs((f.bbox[1] + f.bbox[3]) / 2 - ccy)); lm = f.landmark_2d_106
    ey = float(np.mean([np.ptp(e[:, 1]) / (np.ptp(e[:, 0]) + 1e-6) for e in (lm[33:43], lm[87:97])])); sm = float(np.ptp(lm[52:72][:, 0]) / (f.bbox[2] - f.bbox[0]))
    eye[r.face_id], smile[r.face_id] = ey, sm; cache[r.face_id] = [ey, sm]
EXPR.write_text(json.dumps(cache)); print(f"features done in {(time.time()-t0)/60:.1f} min")
faces["face_sharp"] = faces.face_id.map(sharp); faces["eye"] = faces.face_id.map(eye); faces["smile"] = faces.face_id.map(smile)

# ---- look score (global percentiles) + within-person rank ------------------------------------------
pct = lambda s: s.rank(pct=True)
faces["look"] = 0.40 * pct(faces.face_sharp) + 0.15 * pct(faces.det_score) + 0.25 * pct(faces.eye.fillna(faces.eye.median())) + 0.10 * pct(faces.smile.fillna(faces.smile.median())) + 0.10 * pct(faces.sharpness)
faces["blink"] = (faces.eye < 0.14).astype(int)
faces.loc[faces.blink == 1, "look"] -= 0.30; faces.loc[faces.edge == 1, "look"] -= 0.20
faces["look_rank"] = faces.groupby("cluster_id")["look"].rank(pct=True)
faces["good"] = ((faces.look_rank >= 0.45) & (faces.blink == 0) & (faces.edge == 0)).astype(int)
out_cols = ["face_id", "photo_id", "cluster_id", "gallery", "size", "det_score", "prom", "n_faces", "role", "edge", "face_sharp", "eye", "smile", "blink", "look", "look_rank", "good", "t"]
faces[out_cols].to_parquet(D / "photo_people.parquet", index=False)
print(faces.role.value_counts().to_dict(), "| good:", int(faces.good.sum()))

# ---- highlights per person -------------------------------------------------------------------------
ppl_sets = faces[faces["size"] >= 60].groupby("photo_id").cluster_id.apply(frozenset)
def scenes(df):
    df = df.sort_values("t"); ids, cur, last = [], -1, None
    for r in df.itertuples():
        A = ppl_sets.get(r.photo_id, frozenset()); B = ppl_sets.get(last.photo_id, frozenset()) if last is not None else frozenset()
        new = last is None or r.gallery != last.gallery or (r.t - last.t).total_seconds() > 120 or len(A & B) / max(1, len(A | B)) < 0.34
        cur += int(new); ids.append(cur); last = r
    return pd.Series(ids, index=df.index)
with_couple = faces[faces.cluster_id.isin(COUPLE)].groupby("photo_id").cluster_id.apply(set)
HL = {}
people = [c for c, n in faces.groupby("cluster_id").photo_id.nunique().items() if n >= 5 and c not in exclude]
for cid in tqdm(people, mininterval=5):
    m = faces[faces.cluster_id == cid].copy(); m["scene"] = scenes(m)
    ok = m[(m.good == 1) & (m.role != "background")].sort_values("look", ascending=False)
    pick, used = [], set()
    def take(df, n, tag):
        for r in df.itertuples():
            if len([p for p in pick if p["bucket"] == tag]) >= n: break
            if r.scene in used: continue
            used.add(r.scene); pick.append(dict(photo_id=r.photo_id, bucket=tag, role=r.role, look=round(float(r.look), 3), prom=round(float(r.prom), 2), n_faces=int(r.n_faces), gallery=r.gallery, t=r.t.strftime("%Y-%m-%d %H:%M")))
    if cid not in COUPLE:
        take(ok[ok.photo_id.map(lambda p: bool(with_couple.get(p)))], 5, "with_couple")
    else:
        other = list(COUPLE - {cid})[0]; take(ok[ok.photo_id.map(lambda p: other in with_couple.get(p, set()))], 6, "with_couple")
    take(ok[ok.role == "focus"], 12, "focus"); take(ok[ok.role == "group"], 8, "group")
    if len(pick) < BUDGET: take(ok[ok.role == "focus"], 12 + (BUDGET - len(pick)), "focus")
    pick.sort(key=lambda p: p["t"])
    HL[int(cid)] = dict(n_photos=int(m.photo_id.nunique()), n_good=int(ok.photo_id.nunique()), roles=m.role.value_counts().to_dict(), picks=pick[:BUDGET])
(D / "highlights.json").write_text(json.dumps(HL))
print(f"highlights for {len(HL)} people → data/highlights.json")
