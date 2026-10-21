"""
EXPERIMENT (lives outside the site): compare ways of picking a guest's ~25 best photos.
  python experiments/curate_experiment.py --cluster 15 --name Neel [--budget 25]
Writes experiments/curation/<slug>.html (+ img/ thumbs). Open in a browser; ♥ votes are saved in localStorage; "Export votes" downloads JSON.

Strategies (individual = photos with ≤5 usable faces; GROUP photos are a separate section):
  A quality      face sharpness + detector confidence + face size + frame focus
  B prominence   you must be a main subject: your face ≥60% of the largest face, ≤4 faces
  C expression   A + eyes-open + smile (facial landmarks run only on candidates)
  D diversity    round-robin across events, then spread across moments
  E social       with your top co-stars, small groups (2–6 faces), you prominent
  F with-couple  with Preethi/Neel (or the other half, for the couple), ≤4 faces
  G groups       ≥6 faces, one per moment, biggest groups first — SEPARATE section
"""
import argparse, json, re, math
from pathlib import Path
import numpy as np, pandas as pd, cv2
from PIL import Image

ap = argparse.ArgumentParser(); ap.add_argument("--cluster", type=int, required=True); ap.add_argument("--name", required=True); ap.add_argument("--budget", type=int, default=25)
a = ap.parse_args(); slug = re.sub(r"\W+", "-", a.name.lower()).strip("-")
ROOT = Path(__file__).resolve().parent.parent; D, CACHE = ROOT / "data", ROOT / "cache"; OUT = ROOT / "experiments" / "curation"; IMG = OUT / "img"; IMG.mkdir(parents=True, exist_ok=True)
COUPLE = {15, 50}; labels = json.loads((D / "labels.json").read_text()) if (D / "labels.json").exists() else {}
name_of = lambda c: labels.get(str(c), {}).get("name") or f"#{c}"

faces = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
faces = faces[(faces.det_score >= .65) & (faces["size"] >= 36)]
photos = pd.read_parquet(D / "photos.parquet").merge(pd.read_parquet(D / "photo_features.parquet"), on="photo_id")
photos["t"] = pd.to_datetime(photos.taken_at, format="%Y:%m:%d %H:%M:%S", errors="coerce")
EVN = {"GREH SHANTI": "Greh Shanti", "HALDI": "Haldi", "SANGEET": "Sangeet", "GROOM MORNING": "Groom's morning", "BRIDE MORNING": "Bride's morning", "COUPLE SHOOT": "Couple shoot", "WEDDING": "Wedding", "RECEPTION COUPLE": "Reception portraits", "RECEPTION PARTY": "Reception"}

# ---- my photos + per-photo context ---------------------------------------------------
per_photo = faces.groupby("photo_id").agg(n_usable=("face_id", "count"), max_face=("size", "max"))
mine = faces[faces.cluster_id == a.cluster].sort_values("det_score", ascending=False).drop_duplicates("photo_id")
mine = mine.merge(photos, on=["photo_id", "gallery"]).merge(per_photo, left_on="photo_id", right_index=True).sort_values("t").reset_index(drop=True)
mine["prom"] = mine["size"] / mine.max_face
others = faces[faces.photo_id.isin(mine.photo_id) & (faces.cluster_id != a.cluster)]
mine["who"] = mine.photo_id.map(others.groupby("photo_id").cluster_id.apply(lambda s: sorted(set(int(x) for x in s)))).apply(lambda v: v if isinstance(v, list) else [])
def face_sharp(r):
    img = cv2.imread(str(CACHE / r.photo_id), cv2.IMREAD_GRAYSCALE); c = img[max(0, int(r.y1)):int(r.y2), max(0, int(r.x1)):int(r.x2)]
    return float(cv2.Laplacian(cv2.resize(c, (128, 128)), cv2.CV_64F).var()) if c.size > 100 else 0.0
mine["face_sharp"] = [face_sharp(r) for r in mine.itertuples()]
rank = lambda s: s.rank(pct=True)
mine["q"] = 0.40 * rank(mine.face_sharp) + 0.25 * rank(mine.det_score) + 0.20 * rank(mine["size"]) + 0.15 * rank(mine.sharpness)
# edge penalty: face cut by frame
mine["edge"] = ((mine.x1 < 8) | (mine.y1 < 8) | (mine.x2 > mine.w - 8) | (mine.y2 > mine.h - 8)).astype(int)
mine.loc[mine.edge == 1, "q"] -= 0.25

# scenes (same rule as the site)
ppl = faces[faces["size"] >= 60].groupby("photo_id").cluster_id.apply(frozenset); mine["ppl"] = mine.photo_id.map(ppl).apply(lambda s: s if isinstance(s, frozenset) else frozenset())
scene, cur, last = [], -1, None
for r in mine.itertuples():
    new = last is None or r.gallery != last.gallery or (r.t - last.t).total_seconds() > 120 or len(r.ppl & last.ppl) / max(1, len(r.ppl | last.ppl)) < 0.34
    if new: cur += 1
    scene.append(cur); last = r
mine["scene"] = scene
print(f"{a.name}: {len(mine)} photos, {mine.scene.nunique()} scenes; groups(≥6 faces)={int((mine.n_usable>=6).sum())}")

# ---- expression (landmarks) on candidates only ------------------------------------------
cand = mine[(mine.n_usable <= 5) & (mine.prom >= 0.4)].sort_values("q", ascending=False).head(320)
from insightface.app import FaceAnalysis
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"], allowed_modules=["detection", "landmark_2d_106"]); app.prepare(ctx_id=0, det_size=(320, 320))
EXPR = D / "expr_cache.json"; ecache = json.loads(EXPR.read_text()) if EXPR.exists() else {}
eye, smile = {}, {}
for r in cand.itertuples():
    ck = f"{r.photo_id}|{a.cluster}"
    if ck in ecache: eye[r.photo_id], smile[r.photo_id] = ecache[ck]; continue
    img = cv2.imread(str(CACHE / r.photo_id)); H, W = img.shape[:2]; bw, bh = r.x2 - r.x1, r.y2 - r.y1
    x1, y1, x2, y2 = int(max(0, r.x1 - bw)), int(max(0, r.y1 - bh)), int(min(W, r.x2 + bw)), int(min(H, r.y2 + bh))
    fs = app.get(img[y1:y2, x1:x2])
    if not fs: continue
    cx, cy = (x2 - x1) / 2, (y2 - y1) / 2; f = min(fs, key=lambda f: abs((f.bbox[0] + f.bbox[2]) / 2 - cx) + abs((f.bbox[1] + f.bbox[3]) / 2 - cy)); lm = f.landmark_2d_106
    re_, le_ = lm[33:43], lm[87:97]; ey = np.mean([(np.ptp(e[:, 1])) / (np.ptp(e[:, 0]) + 1e-6) for e in (re_, le_)])
    m = lm[52:72]; sm = np.ptp(m[:, 0]) / (f.bbox[2] - f.bbox[0])
    eye[r.photo_id] = float(ey); smile[r.photo_id] = float(sm); ecache[ck] = [float(ey), float(sm)]
EXPR.write_text(json.dumps(ecache))
mine["eye"] = mine.photo_id.map(eye); mine["smile"] = mine.photo_id.map(smile)
mine["expr"] = 0.5 * mine.q + 0.3 * rank(mine.eye.fillna(mine.eye.median())) + 0.2 * rank(mine.smile.fillna(mine.smile.median()))
mine.loc[mine.eye < 0.14, "expr"] -= 0.3   # likely blink

# ---- strategies -----------------------------------------------------------------------------
B = a.budget
def one_per_scene(df, key, n=B):
    df = df.sort_values(key, ascending=False).drop_duplicates("scene"); return df.head(n)
indiv = mine[mine.n_usable <= 5]
S = {}
S["A · Quality"] = one_per_scene(indiv, "q")
S["B · Prominence"] = one_per_scene(indiv[(indiv.prom >= 0.6) & (indiv.n_usable <= 4)], "q")
S["C · Expression"] = one_per_scene(indiv, "expr")
# D diversity: round-robin across events by q, one per scene, then fill
d_rows, pools = [], {e: g.sort_values("q", ascending=False).drop_duplicates("scene").itertuples() for e, g in indiv.groupby("gallery")}
seen = set()
while len(d_rows) < B and pools:
    for e in list(pools):
        try:
            r = next(pools[e])
            if r.scene in seen: continue
            d_rows.append(r._asdict()); seen.add(r.scene)
            if len(d_rows) >= B: break
        except StopIteration: pools.pop(e)
S["D · Diversity"] = pd.DataFrame(d_rows)
top_co = others.groupby("cluster_id").photo_id.nunique().sort_values(ascending=False); top_co = [int(c) for c in top_co.index if c not in COUPLE][:6]
soc = indiv[(indiv.n_usable.between(2, 6)) & (indiv.prom >= 0.5) & indiv.who.apply(lambda w: any(c in top_co for c in w))]
S["E · Social (with your people)"] = one_per_scene(soc, "q")
other_half = list(COUPLE - {a.cluster}) if a.cluster in COUPLE else list(COUPLE)
wc = indiv[indiv.who.apply(lambda w: any(c in other_half for c in w)) & (indiv.n_usable <= 4)]
S["F · With " + (" & ".join(name_of(c) for c in other_half))] = one_per_scene(wc, "q")
groups = mine[mine.n_usable >= 6].sort_values(["n_usable", "q"], ascending=False).drop_duplicates("scene").head(18)

# ---- overlap matrix ---------------------------------------------------------------------------
keys = list(S); sets = {k: set(S[k].photo_id) for k in keys}
overlap = [[len(sets[i] & sets[j]) for j in keys] for i in keys]
in_n = {}
for k in keys:
    for p in sets[k]: in_n[p] = in_n.get(p, 0) + 1

# ---- images + page --------------------------------------------------------------------------------
def thumb(pid, side=720):
    dst = IMG / pid; dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        im = Image.open(CACHE / pid); im.thumbnail((side, side)); im.save(dst, quality=82)
    return f"img/{pid}"
FACES_DIR = OUT / "faces"; FACES_DIR.mkdir(exist_ok=True)
allf = faces  # usable faces
def face_crop(f):
    dst = FACES_DIR / (re.sub(r"[^\w.-]", "_", f.face_id) + ".jpg")
    if not dst.exists():
        img = cv2.imread(str(CACHE / f.photo_id)); H, W = img.shape[:2]; bw, bh = f.x2 - f.x1, f.y2 - f.y1
        x1, y1, x2, y2 = int(max(0, f.x1 - .4 * bw)), int(max(0, f.y1 - .5 * bh)), int(min(W, f.x2 + .4 * bw)), int(min(H, f.y2 + .4 * bh))
        cv2.imwrite(str(dst), cv2.resize(img[y1:y2, x1:x2], (96, 96)), [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f"faces/{dst.name}"
def people_strip(pid):
    ff = allf[allf.photo_id == pid].sort_values("size", ascending=False)
    items = []
    for f in ff.itertuples():
        cid = int(f.cluster_id); nm = labels.get(str(cid), {}).get("name"); me = cid == a.cluster
        items.append(f'<div class=pp data-cid="{cid}"><img src="{face_crop(f)}" title="#{cid}"><span class=nm>{"<b>" + (nm or "#%d" % cid) + "</b>" if me else (nm or "#%d" % cid)}</span>'
                     f'<span class=gb><button class=g data-v=good title="good photo of them">👍</button><button class=g data-v=bad title="bad photo of them">👎</button></span></div>')
    return "".join(items)
def tile(r):
    who = ", ".join(name_of(c) for c in r.who[:4]) + (" +%d" % (len(r.who) - 4) if len(r.who) > 4 else "")
    ex = "" if pd.isna(r.eye) else f" · eye {r.eye:.2f} · smile {r.smile:.2f}"
    return (f'<figure data-p="{r.photo_id}" data-c="{CACHE / r.photo_id}"><img loading=lazy src="{thumb(r.photo_id)}"><span class=sc></span>'
            f'<figcaption><b>{EVN.get(r.gallery, r.gallery)}</b> · {r.t.strftime("%-I:%M %p")} · {int(r.n_usable)} face{"s" if r.n_usable != 1 else ""} · prom {r.prom:.2f}<br>'
            f'q {r.q:.2f}{ex}{(" · in " + str(in_n.get(r.photo_id, 0)) + " strategies") if in_n.get(r.photo_id, 0) > 1 else ""}</figcaption>'
            f'<div class=rate><label>score <output>0</output></label><input type=range min=-5 max=5 value=0 step=1 class=score><textarea class=cm rows=1 placeholder="comment…"></textarea></div>'
            f'<div class=who><small>who\'s in it — good photo of them?</small>{people_strip(r.photo_id)}</div></figure>')
sections = "".join(f'<section><h2>{k} <small>{len(S[k])} photos · {S[k].scene.nunique() if len(S[k]) else 0} moments</small></h2><p class=d>{DESC[k[0]]}</p><div class=g>{"".join(tile(r) for r in S[k].itertuples())}</div></section>' for k in keys) if (DESC := {
    "A": "Highest technical quality of *your* face and the frame — the current site rule.", "B": "You must be a main subject: your face is ≥60% the size of the largest face, ≤4 people. Filters out background appearances.",
    "C": "Quality plus facial landmarks: eyes open (blink penalty) and a wider smile score higher. Landmarks run only on candidates.", "D": "Even spread across the events you attended, one per moment — sacrifices peak quality for coverage.",
    "E": "Small-group shots with your most-photographed people, you clearly in frame — the ‘your people’ bucket.", "F": "Photos with the couple (or the other half), ≤4 people — the ‘proof of presence’ bucket."}) else ""
grp = "".join(tile(r) for r in groups.itertuples())
ov = "<table><tr><th></th>" + "".join(f"<th>{k[0]}</th>" for k in keys) + "</tr>" + "".join(f"<tr><th>{keys[i]}</th>" + "".join(f"<td{' class=diag' if i == j else ''}>{overlap[i][j]}</td>" for j in range(len(keys))) + "</tr>" for i in range(len(keys))) + "</table>"
html = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Curation experiment — {a.name}</title>
<style>
:root{{--bg:#f6f4ef;--panel:#fff;--ink:#1a1a19;--muted:#6b6963;--line:#e4e1d8;--acc:#b8862b;--rose:#c8462f}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
header{{position:sticky;top:0;background:var(--panel);border-bottom:1px solid var(--line);padding:10px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:5}}
header h1{{font-size:17px;margin:0;font-weight:600}}header nav a{{color:var(--acc);text-decoration:none;margin-right:12px;font-size:13px}}
header .r{{margin-left:auto;display:flex;gap:8px;align-items:center;font-size:13px}}button.x{{font:inherit;font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);cursor:pointer}}
main{{padding:16px 22px;max-width:1700px;margin:0 auto}}section{{margin-bottom:34px}}h2{{font-size:20px;margin:0 0 4px}}h2 small{{font-size:13px;color:var(--muted);font-weight:400;margin-left:8px}}.d{{color:var(--muted);margin:0 0 10px;font-size:13px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}}figure{{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative}}
figure img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;cursor:zoom-in}}figcaption{{padding:6px 9px 8px;font-size:11px;color:var(--muted);line-height:1.35}}figcaption b{{color:var(--ink)}}
.sc{{position:absolute;top:6px;right:6px;min-width:30px;height:30px;line-height:30px;text-align:center;border-radius:15px;background:rgba(0,0,0,.5);color:#fff;font-size:13px;font-weight:600;padding:0 8px;display:none}}
figure.rated .sc{{display:block}}figure.pos{{outline:3px solid #1b8f5a}}figure.neg{{outline:3px solid var(--rose)}}
.rate{{padding:4px 9px 6px;border-top:1px solid var(--line);display:grid;grid-template-columns:auto 1fr;gap:4px 8px;align-items:center;font-size:12px}}.rate label{{color:var(--muted)}}.rate output{{font-weight:600;color:var(--ink);margin-left:4px}}
.rate input[type=range]{{width:100%;accent-color:var(--acc)}}.rate textarea{{grid-column:1/-1;font:inherit;font-size:12px;border:1px solid var(--line);border-radius:6px;padding:4px 6px;resize:vertical;width:100%}}
.who{{padding:6px 9px 8px;border-top:1px solid var(--line);font-size:12px}}.who small{{display:block;color:var(--muted);margin-bottom:4px}}
.pp{{display:flex;align-items:center;gap:6px;padding:2px 0}}.pp img{{width:28px;height:28px;border-radius:50%;object-fit:cover}}.pp .nm{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.pp .g{{border:1px solid var(--line);background:#fff;border-radius:6px;padding:1px 6px;cursor:pointer;font-size:12px;opacity:.55}}.pp .g.on{{opacity:1;border-color:var(--ink);background:#f1eee6}}
table{{border-collapse:collapse;font-size:13px;background:var(--panel)}}th,td{{border:1px solid var(--line);padding:5px 10px;text-align:center}}th{{text-align:left;font-weight:600;color:var(--muted)}}td.diag{{background:#f1eee6;font-weight:600}}
#lb{{position:fixed;inset:0;background:rgba(0,0,0,.93);display:none;align-items:center;justify-content:center;z-index:50}}#lb.on{{display:flex}}#lb img{{max-width:96vw;max-height:94vh}}
.note{{background:#fff8e6;border:1px solid #f0dfae;border-radius:8px;padding:8px 12px;font-size:13px;margin:0 0 16px}}
</style></head><body>
<header><h1>Curation experiment — {a.name}</h1><nav>{"".join(f'<a href="#s{i}">{k[0]}</a>' for i, k in enumerate(keys))}<a href="#groups">Groups</a><a href="#overlap">Overlap</a></nav>
<div class=r><span id=fc>0 rated</span><button class=x id=exp>Export votes</button><button class=x id=clr>Clear</button><a href="{'preethi' if slug=='neel' else 'neel'}.html" style="color:var(--acc);margin-left:8px">→ {'Preethi' if slug=='neel' else 'Neel'}</a></div></header>
<main><p class=note>Same {B}-photo budget per strategy. For each photo: score it −5…+5 (would you want it? 0 = meh), add a comment, and for everyone in it say whether it's a good photo <i>of them</i>. Everything is saved in this browser; export when done. Group photos are their own section (never mixed into individual picks). Click a photo to view full size.</p>
{"".join(sec.replace("<section>", f"<section id=s{i}>", 1) for i, sec in enumerate(sections.split("</section>")[:-1]))}
<section id=groups><h2>G · Group photos <small>{len(groups)} · ≥6 faces, biggest first, one per moment</small></h2><p class=d>Separate bucket by design: everyone in the shot gets it, prominence rules don't apply.</p><div class=g>{grp}</div></section>
<section id=overlap><h2>Overlap between strategies <small>photos in common</small></h2>{ov}</section></main>
<div id=lb onclick="this.classList.remove('on')"><img id=lbi></div>
<script>
const KEY='curation-votes-{slug}';let V=JSON.parse(localStorage.getItem(KEY)||'{{}}');const save=()=>localStorage.setItem(KEY,JSON.stringify(V));
function ent(p){{return V[p]||(V[p]={{score:0,comment:'',people:{{}}}})}}
function paint(){{document.querySelectorAll('figure').forEach(f=>{{const v=V[f.dataset.p];const sc=f.querySelector('.sc'),rg=f.querySelector('.score'),cm=f.querySelector('.cm'),o=f.querySelector('output');
  const s=v?v.score:0;rg.value=s;o.textContent=(s>0?'+':'')+s;cm.value=v?v.comment||'':'';sc.textContent=(s>0?'+':'')+s;f.classList.toggle('rated',!!v&&(v.score!==0||v.comment));f.classList.toggle('pos',!!v&&v.score>0);f.classList.toggle('neg',!!v&&v.score<0);
  f.querySelectorAll('.pp').forEach(pp=>{{const g=v&&v.people&&v.people[pp.dataset.cid];pp.querySelectorAll('.g').forEach(b=>b.classList.toggle('on',b.dataset.v===g))}})}});
  const n=Object.values(V).filter(v=>v.score!==0||v.comment||Object.keys(v.people||{{}}).length).length;document.getElementById('fc').textContent=n+' rated'}}
document.querySelectorAll('figure').forEach(f=>{{const p=f.dataset.p;
  f.querySelector('.score').oninput=e=>{{ent(p).score=+e.target.value;save();paint()}};
  f.querySelector('.cm').oninput=e=>{{ent(p).comment=e.target.value;save();paint()}};
  f.querySelectorAll('.pp .g').forEach(b=>b.onclick=()=>{{const cid=b.parentElement.parentElement.dataset.cid;const e=ent(p);e.people[cid]=e.people[cid]===b.dataset.v?undefined:b.dataset.v;if(!e.people[cid])delete e.people[cid];save();paint()}});
  f.querySelector('img').onclick=()=>{{document.getElementById('lbi').src='file://'+f.dataset.c;document.getElementById('lb').classList.add('on')}}}});
document.getElementById('exp').onclick=()=>{{const rows=Object.entries(V).map(([p,v])=>({{photo:p,...v}}));const blob=new Blob([JSON.stringify({{person:'{slug}',rated:rows}},null,1)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ratings-{slug}.json';a.click()}};
document.getElementById('clr').onclick=()=>{{if(confirm('Clear all ratings?')){{V={{}};save();paint()}}}};paint();
</script></body></html>"""
(OUT / f"{slug}.html").write_text(html)
print("→", OUT / f"{slug}.html"); print("overlap:", dict(zip([k[0] for k in keys], overlap)))
