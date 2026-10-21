"""
Per-photo visual features used for scene grouping + best-shot selection.
  phash      64-bit perceptual hash (near-duplicate / same-scene detection)
  sharpness  variance of Laplacian on a 1000px grey copy (global focus)
Writes data/photo_features.parquet.  Run once after extract_faces.py.
"""
import numpy as np, pandas as pd, cv2, imagehash
from PIL import Image
from pathlib import Path
from tqdm import tqdm

HERE = Path(__file__).parent; CACHE = HERE / "cache"; D = HERE / "data"
photos = pd.read_parquet(D / "photos.parquet")
rows = []
for r in tqdm(photos.itertuples(), total=len(photos), mininterval=5):
    p = CACHE / r.photo_id
    im = Image.open(p); im.draft("L", (1000, 1000)); g = np.asarray(im.convert("L"))
    if max(g.shape) > 1000:
        s = 1000 / max(g.shape); g = cv2.resize(g, (int(g.shape[1]*s), int(g.shape[0]*s)))
    rows.append(dict(photo_id=r.photo_id, phash=str(imagehash.phash(Image.fromarray(g), hash_size=8)),
                     sharpness=float(cv2.Laplacian(g, cv2.CV_64F).var())))
pd.DataFrame(rows).to_parquet(D / "photo_features.parquet", index=False)
print("wrote", len(rows))
