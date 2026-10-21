"""
Step 1: downscale + cache every photo, then detect faces + embeddings.

Usage:  python extract_faces.py SRC [SRC ...]
  SRC can be a folder or a glob, e.g.  ~/Downloads/neilandpreethi-photo-download-*of26/*
  Gallery name = the photo's parent folder, normalised ("GREH_SHANTI-part2" -> "GREH SHANTI").

Outputs:
  cache/<GALLERY>/<file>.jpg    2560px-max copies (fast to read; used by every later step)
  data/photos.parquet           one row per photo
  data/faces.parquet            one row per face (bbox in cache-pixel coords, 512-d embedding)
Incremental: already-processed photos are skipped.
"""
import sys, os, re, glob, time
from pathlib import Path
import numpy as np, pandas as pd, cv2
from PIL import Image, ImageOps
from tqdm import tqdm

HERE = Path(__file__).parent
CACHE, OUT = HERE / "cache", HERE / "data"; OUT.mkdir(exist_ok=True)
FACES, PHOTOS = OUT / "faces.parquet", OUT / "photos.parquet"
CACHE_SIDE = 2560            # keep small faces in wide group shots detectable
DET_SIZE = 960               # detector input; 640 is default, 960 helps crowds (~1.6x slower)
EXTS = {".jpg", ".jpeg", ".png"}

def gallery_name(folder: str) -> str:
    return re.sub(r"[-_ ]?part\s*\d+$", "", folder, flags=re.I).replace("_", " ").strip().upper()

def load_reduced(p: Path):
    """Decode JPEG at reduced scale (fast), fix EXIF rotation, cap at CACHE_SIDE. Returns (PIL img, exif dt)."""
    im = Image.open(p)
    ex = im.getexif(); dt = None
    try: dt = ex.get_ifd(0x8769).get(36867) or ex.get(306)
    except Exception: pass
    im.draft("RGB", (CACHE_SIDE, CACHE_SIDE))       # DCT-domain downscale: decodes 42MB in ~0.1s
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((CACHE_SIDE, CACHE_SIDE), Image.LANCZOS)
    return im, (str(dt) if dt else None)

def main():
    srcs = []
    for a in sys.argv[1:]:
        srcs += [Path(x) for x in glob.glob(os.path.expanduser(a))] or [Path(a).expanduser()]
    files = sorted({Path(dp) / f for s in srcs for dp, _, fs in os.walk(s, followlinks=True)
                    for f in fs if Path(f).suffix.lower() in EXTS and not f.startswith(".")})
    done = set(pd.read_parquet(PHOTOS)["photo_id"]) if PHOTOS.exists() else set()
    todo = [(f"{gallery_name(p.parent.name)}/{p.stem}.jpg", p) for p in files]
    todo = [(pid, p) for pid, p in todo if pid not in done]
    print(f"{len(files)} photos found, {len(todo)} to process (skipping {len(done)} done)")
    if not todo: return

    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"], allowed_modules=["detection", "recognition"])
    app.prepare(ctx_id=0, det_size=(DET_SIZE, DET_SIZE))

    face_rows, photo_rows, t0 = [], [], time.time()
    for pid, p in tqdm(todo, unit="img", mininterval=5):
        gallery = pid.split("/")[0]
        try:
            im, dt = load_reduced(p)
        except Exception as e:
            photo_rows.append(dict(photo_id=pid, gallery=gallery, src=str(p), taken_at=None, w=0, h=0, n_faces=-1)); continue
        cp = CACHE / pid; cp.parent.mkdir(parents=True, exist_ok=True)
        if not cp.exists(): im.save(cp, quality=88, optimize=True)
        img = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR); h, w = img.shape[:2]
        faces = app.get(img)
        for i, f in enumerate(faces):
            x1, y1, x2, y2 = f.bbox.tolist()
            face_rows.append(dict(face_id=f"{pid}#{i}", photo_id=pid, gallery=gallery,
                                  x1=x1, y1=y1, x2=x2, y2=y2, size=max(x2-x1, y2-y1),
                                  det_score=float(f.det_score),
                                  emb=f.normed_embedding.astype(np.float32).tolist()))
        photo_rows.append(dict(photo_id=pid, gallery=gallery, src=str(p), taken_at=dt, w=w, h=h, n_faces=len(faces)))
        if len(photo_rows) >= 100: flush(face_rows, photo_rows); face_rows, photo_rows = [], []
    flush(face_rows, photo_rows)
    print(f"done in {time.time()-t0:.0f}s ({(time.time()-t0)/len(todo):.2f}s/img)")

def flush(face_rows, photo_rows):
    for rows, path in ((photo_rows, PHOTOS), (face_rows, FACES)):
        if rows:
            df = pd.DataFrame(rows)
            if path.exists(): df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
            df.to_parquet(path, index=False)

if __name__ == "__main__":
    main()
