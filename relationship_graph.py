"""
Side EDA: who is photographed with whom.
Nodes = people (clusters with >= MIN_PHOTOS photos), size ~ sqrt(photos).
Edges = photos together (usable faces), width ~ log(photos together), drawn if >= MIN_TOGETHER.
Communities via Louvain on the graph WITHOUT the couple (they connect to everyone and would blur the groups).
Writes data/relationship_graph.html (self-contained; face thumbnails inlined) + data/relationship_communities.csv
"""
import json, base64, math
from pathlib import Path
from itertools import combinations
from collections import Counter, defaultdict
import numpy as np, pandas as pd, cv2, networkx as nx

HERE = Path(__file__).parent; D, CACHE = HERE / "data", HERE / "cache"
import sys
COUPLE = {15, 50}
MIN_PHOTOS, MIN_TOGETHER, TOPK = 50, 4, 3
def build(min_photos=50, min_together=4, topk=3, faces_as_uri=True):
    global MIN_PHOTOS, MIN_TOGETHER, TOPK
    MIN_PHOTOS, MIN_TOGETHER, TOPK = min_photos, min_together, topk
    global labels, exclude, name_of, faces, G, DIV, PAL, COUPLE_COL, comm_summary
    labels = json.loads((D / "labels.json").read_text()) if (D / "labels.json").exists() else {}
    exclude = set(json.loads((D / "exclude.json").read_text())) if (D / "exclude.json").exists() else set()
    name_of = lambda c: labels.get(str(c), {}).get("name") or f"#{c}"

    faces = pd.read_parquet(D / "faces.parquet").merge(pd.read_parquet(D / "clusters.parquet")[["face_id", "cluster_id"]], on="face_id")
    faces = faces[(faces.det_score >= .65) & (faces["size"] >= 36) & ~faces.cluster_id.isin(exclude)]
    photos_per = faces.groupby("cluster_id").photo_id.nunique()
    nodes = set(photos_per[photos_per >= MIN_PHOTOS].index)
    by_photo = faces[faces.cluster_id.isin(nodes)].groupby("photo_id").cluster_id.apply(lambda s: sorted(set(s)))
    pair = Counter(p for ppl in by_photo for p in combinations(ppl, 2))
    edges = {p: w for p, w in pair.items() if w >= MIN_TOGETHER}
    print(f"{len(nodes)} people, {len(edges)} edges (≥{MIN_TOGETHER} photos together)")

    G = nx.Graph()
    for c in nodes: G.add_node(int(c), photos=int(photos_per[c]))
    for (a, b), w in edges.items(): G.add_edge(int(a), int(b), weight=int(w))
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0 and n not in COUPLE])

    # communities on the graph minus the couple
    H = G.copy(); H.remove_nodes_from(COUPLE)
    comms = nx.community.louvain_communities(H, weight="weight", resolution=1.0, seed=7)
    comms = sorted(comms, key=len, reverse=True)
    comm_of = {n: i for i, c in enumerate(comms) for n in c}
    for n in COUPLE: comm_of[n] = -1
    # fold communities beyond 7 into "other"
    for n, i in comm_of.items():
        if i >= 7: comm_of[n] = 7
    print("communities:", [len(c) for c in comms])

    # bride-side vs groom-side affinity, seeded from the parents/sibling, propagated 2 hops through the weighted graph
    BRIDE, GROOM = {110, 622, 1167}, {214, 10}
    def seed_score(n):
        b = sum(G[n][m]["weight"] for m in G[n] if m in BRIDE); g = sum(G[n][m]["weight"] for m in G[n] if m in GROOM)
        return (b - g) / (b + g) if (b + g) >= 6 else None
    side = {n: seed_score(n) for n in G.nodes}
    for n in BRIDE: side[n] = 1.0
    for n in GROOM: side[n] = -1.0
    for _ in range(2):  # propagate to nodes with weak seed signal
        for n in G.nodes:
            if side.get(n) is None or abs(side[n]) < 0.15:
                nb = [(G[n][m]["weight"], side[m]) for m in G[n] if side.get(m) is not None and m not in COUPLE]
                if nb: side[n] = sum(w * v for w, v in nb) / sum(w for w, _ in nb)
    for n in COUPLE: side[n] = 0.0
    DIV = ["#2a78d6", "#86b6ef", "#9a9a94", "#f0a07e", "#eb6834"]  # bride ← neutral → groom (two hues + grey midpoint)
    def side_col(v):
        if v is None: return "#9a9a94"
        return DIV[0] if v > .5 else DIV[1] if v > .15 else DIV[2] if v >= -.15 else DIV[3] if v >= -.5 else DIV[4]

    # ---- deterministic clustered layout (#10) --------------------------------
    # NO spring physics. The existing Louvain communities (seed=7, ordered by
    # size above) drive the geometry: within each community members are ordered
    # by photo count and packed into a compact sunflower blob; the blobs sit on
    # a fixed ring around the pinned couple (bride 15 left, groom 50 right) at
    # the exact centre. Same labels.json in -> identical coordinates out.
    maxp = max(d["photos"] for _, d in G.nodes(data=True))
    r_of = lambda p: 9 + 26 * math.sqrt(p / maxp)
    R = {n: r_of(d["photos"]) for n, d in G.nodes(data=True)}

    # members per community (couple excluded), ordered by photo count then id (deterministic)
    groups = defaultdict(list)
    for n in G.nodes:
        if n in COUPLE: continue
        groups[comm_of.get(n, 7)].append(n)
    for ci in groups:
        groups[ci].sort(key=lambda n: (-G.nodes[n]["photos"], n))
    comm_order = sorted(groups.keys())            # 0..7 ascending == largest community first (7 = 'other')
    NB = len(comm_order)

    GOLDEN = math.pi * (3.0 - math.sqrt(5.0))     # ~2.39996 rad — deterministic sunflower packing
    blob_local, blob_ro = {}, {}
    for ci in comm_order:
        mem = groups[ci]
        maxr = max(R[n] for n in mem)
        C = 1.9 * maxr + 10.0                     # nearest-neighbour spacing inside a blob
        ro = 0.0
        for k, n in enumerate(mem):               # k=0 (most photos) sits at the blob centre
            dist = C * math.sqrt(k)
            ang = k * GOLDEN
            blob_local[n] = (dist * math.cos(ang), dist * math.sin(ang))
            ro = max(ro, dist + R[n])
        blob_ro[ci] = ro

    # ring radius: clears the couple and keeps neighbouring blobs from touching
    coupleR = max((R[c] for c in COUPLE if c in G), default=30.0)
    maxRo = max(blob_ro.values(), default=120.0)
    GAP = 70.0
    if NB <= 1:
        ring = coupleR + maxRo + GAP
    else:
        ring = max(coupleR + maxRo + GAP, (2.0 * maxRo + GAP) / (2.0 * math.sin(math.pi / NB)))

    # blob centres on the ring (12 o'clock, clockwise) -> node positions (couple-relative frame).
    # a horizontal stretch keeps the admin canvas landscape (like the mock) without reducing any
    # blob-to-blob separation — stretching x only pushes neighbouring blobs further apart.
    ASPECT_X = 1.7
    P, comm_center = {}, {}
    for i, ci in enumerate(comm_order):
        th = -math.pi / 2.0 + i * (2.0 * math.pi / NB)
        bx, by = ring * math.cos(th) * ASPECT_X, ring * math.sin(th)
        comm_center[ci] = (bx, by)
        for n in groups[ci]:
            dx, dy = blob_local[n]
            P[n] = [bx + dx, by + dy]

    # pinned couple: bride 15 left, groom 50 right, dead centre — always
    couple_present = [c for c in (15, 50) if c in G]
    if len(couple_present) == 2:
        dc = coupleR + 12.0
        P[couple_present[0]] = [-dc, 0.0]; P[couple_present[1]] = [dc, 0.0]
    elif couple_present:
        P[couple_present[0]] = [0.0, 0.0]

    # mono caption anchor centred under each blob
    comm_label_xy = {ci: (comm_center[ci][0], comm_center[ci][1] + blob_ro[ci] + 30.0) for ci in comm_order}

    # canvas sized SYMMETRICALLY about the couple (local origin), so bride+groom land
    # dead-centre every time regardless of how many blobs ring them
    NAME_ROOM = 20.0
    xs_c = [P[n][0] - R[n] for n in P] + [P[n][0] + R[n] for n in P]
    ys_c = [P[n][1] - R[n] for n in P] + [P[n][1] + R[n] + NAME_ROOM for n in P]
    for lx, ly in comm_label_xy.values():
        xs_c += [lx - 90.0, lx + 90.0]; ys_c += [ly + 14.0]
    PAD = 90.0
    rad_x = max(abs(v) for v in xs_c) + PAD
    rad_y = max(abs(v) for v in ys_c) + PAD
    W = int(round(2.0 * rad_x)); Hh = int(round(2.0 * rad_y))
    ox, oy = W / 2.0, Hh / 2.0                     # couple origin -> exact canvas centre
    pos = {n: (P[n][0] + ox, P[n][1] + oy) for n in P}
    comm_label_xy = {ci: (x + ox, y + oy) for ci, (x, y) in comm_label_xy.items()}
    sx = lambda x: x; sy = lambda y: y
    ids = list(G.nodes)

    # face thumbnails (best face per node) as data URIs
    def face_uri(cid):
        f = faces[faces.cluster_id == cid].sort_values("det_score", ascending=False).iloc[0]
        img = cv2.imread(str(CACHE / f.photo_id)); Hi, Wi = img.shape[:2]; bw, bh = f.x2 - f.x1, f.y2 - f.y1
        x1, y1, x2, y2 = int(max(0, f.x1 - .45 * bw)), int(max(0, f.y1 - .55 * bh)), int(min(Wi, f.x2 + .45 * bw)), int(min(Hi, f.y2 + .45 * bh))
        ok, buf = cv2.imencode(".jpg", cv2.resize(img[y1:y2, x1:x2], (96, 96)), [cv2.IMWRITE_JPEG_QUALITY, 80])
        return "data:image/jpeg;base64," + base64.b64encode(buf).decode()
    if not faces_as_uri:
        face_uri = lambda cid: f"/crop/{faces[faces.cluster_id == cid].sort_values('det_score', ascending=False).iloc[0].face_id}"

    # validated categorical palette (dataviz reference, light mode) — fixed slot order; slot 8 → 'other' grey
    PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#9a9a94"]
    COUPLE_COL = "#1a1a19"
    maxw = max(d["weight"] for _, _, d in G.edges(data=True))
    topk = set()   # each person's strongest TOPK ties -> drawn by default
    for n in G.nodes:
        for w, m in sorted(((G[n][m]["weight"], m) for m in G[n]), reverse=True)[:TOPK]: topk.add(tuple(sorted((n, m))))
    node_js = [dict(id=n, name=name_of(n), photos=d["photos"], x=round(sx(pos[n][0]), 1), y=round(sy(pos[n][1]), 1), r=round(r_of(d["photos"]), 1),
                    comm=comm_of.get(n, 7), col=(COUPLE_COL if n in COUPLE else PAL[comm_of.get(n, 7)]), side=(None if side.get(n) is None else round(side[n], 2)), scol=(COUPLE_COL if n in COUPLE else side_col(side.get(n))), img=face_uri(n), labeled=str(n) in labels)
               for n, d in G.nodes(data=True)]
    edge_js = [dict(s=u, t=v, w=d["weight"], top=int(tuple(sorted((u, v))) in topk), sw=round(0.8 + 5 * math.log1p(d["weight"]) / math.log1p(maxw), 2)) for u, v, d in G.edges(data=True)]

    # community table
    rows = []
    for n, d in G.nodes(data=True):
        nb = sorted(((G[n][m]["weight"], m) for m in G[n]), reverse=True)[:3]
        rows.append(dict(cluster=n, name=name_of(n), community=comm_of.get(n, 7), side=(None if side.get(n) is None else round(side[n], 2)), photos=d["photos"], degree=G.degree(n),
                         top_costars="; ".join(f"{name_of(m)} ({w})" for w, m in nb)))
    tbl = pd.DataFrame(rows).sort_values(["community", "photos"], ascending=[True, False]); tbl.to_csv(D / "relationship_communities.csv", index=False)
    comm_summary = tbl[tbl.community >= 0].groupby("community").agg(people=("cluster", "count"), photos=("photos", "sum"),
        members=("name", lambda s: ", ".join(list(s)[:8]) + (" …" if len(s) > 8 else ""))).reset_index()
    print(comm_summary.to_string(index=False))
    print("\nSide split (non-couple):", pd.Series([side_col(side.get(n)) for n in G.nodes if n not in COUPLE]).map({DIV[0]:"bride",DIV[1]:"lean bride",DIV[2]:"neutral",DIV[3]:"lean groom",DIV[4]:"groom"}).value_counts().to_dict())
    top_pairs = sorted(edges.items(), key=lambda kv: -kv[1])[:15]
    print("\nTop pairs:", [(name_of(a), name_of(b), w) for (a, b), w in top_pairs])

    # per-community mono caption "<NAME> · N" + its on-canvas anchor (the non-colour channel, #10)
    comm_records = json.loads(comm_summary.to_json(orient='records'))
    for rec in comm_records:
        ci = int(rec["community"])
        members = rec.get("members") or ""
        top = members.split(",")[0].strip()
        nm = "Other" if ci == 7 else (top or f"Community {ci + 1}")
        rec["label"] = f"{nm} · {int(rec['people'])}"
        lx, ly = comm_label_xy.get(ci, (W / 2.0, Hh / 2.0))
        rec["lx"] = round(lx, 1); rec["ly"] = round(ly, 1)
    return dict(nodes=node_js, edges=edge_js, communities=comm_records, W=W, H=Hh, PAL=PAL, DIV=DIV, min_photos=MIN_PHOTOS, min_together=MIN_TOGETHER, topk=TOPK)

if __name__ == "__main__":
    R = build(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
    node_js, edge_js, W, Hh, PAL, DIV = R["nodes"], R["edges"], R["W"], R["H"], R["PAL"], R["DIV"]
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>Who was photographed with whom</title>
    <style>
    :root{{--surface:#ffffff;--ink:#1a1a19;--muted:#5f5e58;--grid:#e6e5df}}
    body{{margin:0;background:var(--surface);color:var(--ink);font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
    header{{padding:20px 28px 8px}} h1{{font-size:20px;margin:0 0 4px;font-weight:600}} .sub{{color:var(--muted)}}
    .legend{{display:flex;flex-wrap:wrap;gap:8px 18px;padding:8px 28px 6px;font-size:13px}} .legend span{{display:inline-flex;align-items:center;gap:6px}} .legend i{{width:12px;height:12px;border-radius:50%;display:inline-block}}
    .wrap{{position:relative;margin:0 28px 20px;border:1px solid var(--grid);border-radius:8px;overflow:hidden;background:#fbfbf9}}
    svg{{display:block;width:100%;height:auto;cursor:grab}} svg:active{{cursor:grabbing}}
    line{{stroke:#8a8983;stroke-opacity:.35;stroke-linecap:round}} .dim line{{stroke-opacity:.05}} line.on{{stroke:#1a1a19;stroke-opacity:.75}}
    .node{{cursor:pointer}} .node circle.ring{{fill:none;stroke-width:3}} .dim .node{{opacity:.18}} .node.on,.node.me{{opacity:1}}
    .node text{{font-size:11px;fill:var(--ink);paint-order:stroke;stroke:#fff;stroke-width:3px;pointer-events:none}}
    .tip{{position:absolute;pointer-events:none;background:#1a1a19;color:#fff;padding:8px 10px;border-radius:6px;font-size:12px;line-height:1.35;max-width:260px;display:none;box-shadow:0 6px 20px rgba(0,0,0,.25)}}
    .controls{{padding:0 28px 10px;font-size:13px;color:var(--muted);display:flex;gap:16px;align-items:center}}
    table{{border-collapse:collapse;margin:0 28px 40px;font-size:13px}} th,td{{text-align:left;padding:5px 10px;border-bottom:1px solid var(--grid)}} th{{color:var(--muted);font-weight:600}}
    </style></head><body>
    <header><h1>Who was photographed with whom</h1><div class=sub>{len(node_js)} people with ≥{MIN_PHOTOS} photos · disc size = photos of that person · line width = photos together · by default only each person&rsquo;s {TOPK} strongest ties are drawn (hover a face to see all of theirs) · colour = community (Louvain, computed without the couple) · drag to pan, scroll to zoom</div></header>
    <div class=legend id=legend></div>
    <div class=controls><span>colour by</span><label><input type=radio name=mode value=comm checked> community</label><label><input type=radio name=mode value=side> bride ↔ groom side</label><label style="margin-left:12px"><input type=checkbox id=lbl> all names (default: ≥100 photos, plus hover)</label><label style="margin-left:12px"><input type=checkbox id=allE> all ties</label><label><input type=range id=minw min={MIN_TOGETHER} max=80 value={MIN_TOGETHER}> hide ties under <b id=minwv>{MIN_TOGETHER}</b> photos together</label></div>
    <div class=wrap><svg id=g viewBox="0 0 {W} {Hh}"><defs id=defs></defs><g id=view><g id=edges></g><g id=nodes></g></g></svg><div class=tip id=tip></div></div>
    <h2 style="margin:0 28px 8px;font-size:16px">Communities</h2>
    <table><tr><th>Community</th><th>People</th><th>Photos</th><th>Members (by photo count)</th></tr>
    {''.join(f"<tr><td><i style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{PAL[min(int(r.community),7)]}'></i> {int(r.community)+1}</td><td>{r.people}</td><td>{r.photos}</td><td>{r.members}</td></tr>" for r in comm_summary.itertuples())}
    </table>
    <script>
    const N={json.dumps(node_js)}, E={json.dumps(edge_js)}, PAL={json.dumps(PAL)};
    const byId=Object.fromEntries(N.map(n=>[n.id,n]));
    const svg=document.getElementById('g'), view=document.getElementById('view'), defs=document.getElementById('defs'), gE=document.getElementById('edges'), gN=document.getElementById('nodes'), tip=document.getElementById('tip');
    const NS='http://www.w3.org/2000/svg', el=(t,a={{}})=>{{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e}};
    E.forEach((e,i)=>{{const a=byId[e.s],b=byId[e.t];const l=el('line',{{x1:a.x,y1:a.y,x2:b.x,y2:b.y,'stroke-width':e.sw,'data-w':e.w,'data-s':e.s,'data-t':e.t}});l.dataset.top=e.top;gE.appendChild(l);e.el=l}});
    function applyEdges(){{const all=document.getElementById('allE').checked,mw=+document.getElementById('minw').value;gE.querySelectorAll('line').forEach(l=>l.style.display=((all||l.dataset.top=='1')&&+l.dataset.w>=mw)?'':'none')}};
    N.forEach(n=>{{const cp=el('clipPath',{{id:'c'+n.id}});cp.appendChild(el('circle',{{cx:n.x,cy:n.y,r:n.r}}));defs.appendChild(cp);
     const g=el('g',{{class:'node','data-id':n.id}});g.appendChild(el('circle',{{cx:n.x,cy:n.y,r:n.r+2,fill:'#fff'}}));
     const im=el('image',{{href:n.img,x:n.x-n.r,y:n.y-n.r,width:2*n.r,height:2*n.r,'clip-path':'url(#c'+n.id+')',preserveAspectRatio:'xMidYMid slice'}});g.appendChild(im);
     g.appendChild(el('circle',{{class:'ring',cx:n.x,cy:n.y,r:n.r+1,stroke:n.col,'data-comm':n.col,'data-side':n.scol}}));
     const t=el('text',{{x:n.x,y:n.y+n.r+12,'text-anchor':'middle'}});t.textContent=n.name;t.dataset.big=n.photos>=100?1:0;if(n.photos<100)t.style.display='none';g.appendChild(t);
     g.onmouseenter=ev=>{{svg.classList.add('dim');g.classList.add('me');t.style.display='';const nb=[];E.forEach(e=>{{if(e.s==n.id||e.t==n.id){{e.el.classList.add('on');e.el.style.display='';const o=byId[e.s==n.id?e.t:e.s];nb.push([e.w,o.name]);const og=document.querySelector('.node[data-id="'+o.id+'"]');og.classList.add('on');og.querySelector('text').style.display=''}}}});nb.sort((a,b)=>b[0]-a[0]);
       tip.style.display='block';tip.innerHTML='<b>'+n.name+'</b> — '+n.photos+' photos'+(n.side==null?'':' · side '+(n.side>0?'bride +':'groom ')+Math.abs(n.side).toFixed(2))+'<br>'+nb.slice(0,6).map(x=>x[1]+' <span style="opacity:.7">('+x[0]+')</span>').join('<br>')}};
     g.onmousemove=ev=>{{const r=svg.parentElement.getBoundingClientRect();tip.style.left=(ev.clientX-r.left+14)+'px';tip.style.top=(ev.clientY-r.top+14)+'px'}};
     g.onmouseleave=()=>{{svg.classList.remove('dim');document.querySelectorAll('.on,.me').forEach(x=>x.classList.remove('on','me'));tip.style.display='none';applyEdges();const all=document.getElementById('lbl').checked;gN.querySelectorAll('text').forEach(t=>t.style.display=(all||t.dataset.big=='1')?'':'none')}};
     gN.appendChild(g)}});
    // legend + colour mode
    const DIV={json.dumps(DIV)};
    function legend(mode){{const L=document.getElementById('legend');if(mode=='comm'){{const counts={{}};N.forEach(n=>{{const k=n.comm<0?'couple':n.comm;counts[k]=(counts[k]||0)+1}});
     L.innerHTML=Object.entries(counts).sort((a,b)=>(a[0]=='couple'?-1:b[0]=='couple'?1:a[0]-b[0])).map(([k,c])=>'<span><i style="background:'+(k=='couple'?'#1a1a19':PAL[k])+'"></i>'+(k=='couple'?'The couple':(k==7?'Other':'Community '+(+k+1)))+' · '+c+'</span>').join('')}}
     else{{const names=["Bride's side","Leans bride","Both / unclear","Leans groom","Groom's side"];const cnt=[0,0,0,0,0];N.forEach(n=>{{if(n.comm<0)return;const i=DIV.indexOf(n.scol);if(i>=0)cnt[i]++}});
     L.innerHTML='<span><i style="background:#1a1a19"></i>The couple</span>'+names.map((t,i)=>'<span><i style="background:'+DIV[i]+'"></i>'+t+' · '+cnt[i]+'</span>').join('')}}
     gN.querySelectorAll('.ring').forEach(r=>r.setAttribute('stroke',mode=='comm'?r.dataset.comm:r.dataset.side))}}
    legend('comm');document.querySelectorAll('input[name=mode]').forEach(r=>r.onchange=e=>legend(e.target.value));
    // controls
    document.getElementById('lbl').onchange=e=>gN.querySelectorAll('text').forEach(t=>t.style.display=(e.target.checked||t.dataset.big=='1')?'':'none');
    document.getElementById('minw').oninput=e=>{{document.getElementById('minwv').textContent=e.target.value;applyEdges()}};document.getElementById('allE').onchange=applyEdges;applyEdges();
    // pan/zoom
    let vb=[0,0,{W},{Hh}],drag=null;svg.onmousedown=e=>{{drag=[e.clientX,e.clientY,...vb]}};window.onmouseup=()=>drag=null;
    window.onmousemove=e=>{{if(!drag)return;const s=vb[2]/svg.clientWidth;vb[0]=drag[2]-(e.clientX-drag[0])*s;vb[1]=drag[3]-(e.clientY-drag[1])*s;svg.setAttribute('viewBox',vb.join(' '))}};
    svg.onwheel=e=>{{e.preventDefault();const f=e.deltaY>0?1.1:0.9;const r=svg.getBoundingClientRect();const mx=vb[0]+(e.clientX-r.left)/r.width*vb[2],my=vb[1]+(e.clientY-r.top)/r.height*vb[3];vb=[mx-(mx-vb[0])*f,my-(my-vb[1])*f,vb[2]*f,vb[3]*f];svg.setAttribute('viewBox',vb.join(' '))}};
    </script></body></html>"""
    (D / "relationship_graph.html").write_text(html)
    print("→", D / "relationship_graph.html")
