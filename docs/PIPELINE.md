# Pipeline reference

All scripts run with the repo venv: `.venv/bin/python <script>`. All paths resolve relative to
the script file except `add_scene_scores.py`, which uses a bare `data/` path — **run that one
from the repo root**. Runtimes are on an M1 MacBook with the current corpus (4,206 photos,
26,350 faces).

Order: `extract_faces` → `cluster_and_eda` → `photo_features` → `photo_people` →
`add_scene_scores` → (`relationship_graph`). Steps 1–2 are wrapped by `./run_eda.sh SRC...`.

---

## extract_faces.py — faces + embeddings

```
.venv/bin/python extract_faces.py SRC [SRC ...]
```

- `SRC` = folder or glob of gallery folders, e.g. `photos/*` or
  `"~/Downloads/neilandpreethi-photo-download-*of26/*"`. The photo's **parent folder name**
  becomes the gallery (normalised: `GREH_SHANTI-part2` → `GREH SHANTI`).
- No flags. Constants in-file: `CACHE_SIDE = 2560` (cache copy max side),
  `DET_SIZE = 960` (detector input; default 640, 960 catches small faces in crowds at ~1.6x cost).
- Model: InsightFace **buffalo_l**, CPU provider, modules `detection` + `recognition` only.
- **Outputs:** `cache/<GALLERY>/<file>.jpg` (2560px JPEG q88 — every later step reads these,
  never `photos/`), `data/photos.parquet` (one row/photo: gallery, src, EXIF `taken_at`, w, h,
  n_faces; unreadable files get `n_faces=-1`), `data/faces.parquet` (one row/face: bbox in
  cache-pixel coords, `det_score`, 512-d normalised embedding).
- **Runtime:** ~1.76 s/photo → the full 4.2k corpus took 1 h 45 m. Flushes every 100 photos.
- **Incremental:** photos whose `photo_id` (`GALLERY/stem.jpg`) already exists in
  `photos.parquet` are skipped, so re-runs after adding a gallery only process the new files.
  To force a redo of specific photos, delete their rows from both parquets (or delete both
  parquets + `cache/` for a from-scratch run).

## cluster_and_eda.py — people + EDA

```
.venv/bin/python cluster_and_eda.py [--thresh 0.55] [--min-det 0.65] [--min-size 36] [--top 120]
```

- Quality filter first: faces with `det_score >= --min-det` and box `size >= --min-size` px.
- AgglomerativeClustering, cosine metric, **average** linkage, `distance_threshold = --thresh`
  (0.55 default). Lower = stricter (more fragments of the same person), higher = risks merging
  lookalikes. 0.55 validated by eyeballing contact sheets: only extreme profiles/silhouettes fragment.
- `--top N` (default 120): contact sheets + report cards for the N biggest clusters.
- **Outputs:** `data/clusters.parquet`, `data/people_stats.csv` (photos, galleries, first/last
  seen, tier A ≥15 / B 5–14 / C <5 photos), `data/event_stats.csv`, `data/people_by_event.csv`,
  `data/contact/<cid>.jpg`, `data/eda_report.html` (open it; each card links into the namer at
  `localhost:8792/?cid=`).
- **Runtime:** a couple of minutes (clustering is O(n²) in usable faces; fine at ~20k).
- **Rerun:** cheap and safe, but **cluster ids are not stable across re-clustering** — a re-run
  with different faces or threshold renumbers people and orphans `labels.json`,
  `thresholds.json`, `exclude.json`, and the couple ids in `curation.py` (`COUPLE = {15, 50}`)
  and `relationship_graph.py` (`BRIDE`/`GROOM` seeds). Re-cluster only before labeling, or be
  prepared to re-map labels by hand.

## photo_features.py — phash + sharpness

```
.venv/bin/python photo_features.py
```

- No flags. For every row of `photos.parquet`: 64-bit perceptual hash (near-dup detection) and
  variance-of-Laplacian sharpness on a 1000px grey copy.
- **Output:** `data/photo_features.parquet`. **Runtime:** a few minutes. **Rerun:** full
  recompute, idempotent (overwrites).

## photo_people.py — per-face quality + roles

```
.venv/bin/python photo_people.py
```

- No flags. Constants in-file: `BUDGET = 25`, `COUPLE = {15, 50}`. Honors `data/exclude.json`.
- Per face (det ≥ .65, size ≥ 36):
  - **role** — `focus`: ≤4 faces and their face ≥60% of the largest (or a 2-shot at ≥45%, or solo);
    `group`: ≥5 faces and ≥55% of the largest; `background`: everything else.
  - **look** — 0.40·face-sharpness + 0.15·det + 0.25·eyes-open + 0.10·smile + 0.10·frame
    sharpness (all rank-percentiles), −0.30 if blinking (eye openness < 0.14), −0.20 if the box
    touches a frame edge (8px). Eye/smile come from a second InsightFace pass
    (`landmark_2d_106`) on faces ≥48px, cached in `data/face_expr.json`.
  - `good` = look-rank within the person ≥ 0.45, no blink, no edge.
- **Outputs:** `data/photo_people.parquet`, `data/highlights.json` (legacy picker — the live
  path is `curation.py`; kept for reference).
- **Runtime:** ~36 min first run (landmark pass dominates); re-runs are fast because landmarks
  are cached per `face_id` in `face_expr.json`.

## add_scene_scores.py — score, scenes, auto thresholds

```
cd ~/Downloads/wedding-wrapped && .venv/bin/python add_scene_scores.py
```

- No flags; **must run from the repo root** (uses relative `data/`).
- Adds to `photo_people.parquet`: `score` = global 0–100 percentile of `look` (comparable
  across people) and per-person `scene` ids.
- **Scene rule** (same everywhere in the repo): a new scene starts when the gallery changes,
  the gap to the previous shot exceeds **120 s**, or the Jaccard overlap of people-in-frame
  (faces ≥60px) drops below **0.34**.
- **Auto threshold per person** → `data/thresholds.json`:
  `min(55th percentile of their scores, score of their 30th-best shot)` — i.e. keep at least
  their best `max(30, BUDGET)` photos in play but never admit their bottom 45%. Computed on
  blink/edge-free faces. Entries with `auto: false` (set by hand in the `/highlights` UI) are
  **preserved** on re-runs.
- **Runtime:** seconds. Rerun any time after `photo_people.py`.

## relationship_graph.py — who with whom

```
.venv/bin/python relationship_graph.py [MIN_PHOTOS]     # default 50
```

- Nodes = clusters with ≥ MIN_PHOTOS photos; edges = ≥4 photos together (`min_together`);
  only each node's 3 strongest ties (`topk`) drawn by default. Programmatic API:
  `build(min_photos=50, min_together=4, topk=3, faces_as_uri=True)` — `label_server.py`
  imports and calls this for `/api/graph` (with `faces_as_uri=False`, serving crops over HTTP).
- Communities: Louvain (seed 7) on the graph **minus the couple** (they connect to everyone).
  Communities beyond the 7 largest fold into "other".
- Bride/groom side: seeded from hand-set cluster ids `BRIDE = {110, 622, 1167}`,
  `GROOM = {214, 10}`, propagated 2 hops through edge weights.
- **Outputs:** `data/relationship_graph.html` (self-contained, thumbnails inlined),
  `data/relationship_communities.csv`. **Runtime:** seconds.

## Tuning knobs, in one place

| Knob | Where | Default | Effect |
|---|---|---|---|
| Cluster cut | `cluster_and_eda.py --thresh` | 0.55 | lower = purer but fragmented people |
| Face quality floor | `--min-det` / `--min-size` | 0.65 / 36 px | who counts as "in" a photo |
| Detector input | `extract_faces.py DET_SIZE` | 960 | crowd recall vs speed |
| Scene gap / overlap | in-code, 3 scripts | 120 s / 0.34 | what counts as one "moment" |
| Role cutoffs | `photo_people.py role()` | focus ≥0.60 (0.45 for 2-shots), group ≥0.55 of largest face | focus/group/background split |
| Blink cutoff | `photo_people.py` | eye < 0.14 | blink penalty trigger |
| Auto threshold | `add_scene_scores.py` | min(p55, keep-best-30) | per-person score bar |
| Pick budget | `curation.py BUDGET_HL` | 25 | curated picks per deck |
| Thin-deck floor | `curation.py MIN_PICKS` | 12 | backfill best-available shots below this |
| Couple ids | `curation.py COUPLE` | {15, 50} | drives "with the couple" bucket everywhere |
| Excluded clusters | `data/exclude.json` | [540] | vendors/photographer — dropped from all outputs |
