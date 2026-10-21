"""
Per-MEMBER group map payload: the ego graph + combination photo finder, scoped to the viewer.

The map is rendered by the React deck (app/src/deck/GroupMap.tsx) at the in-deck `#/map`
route — there is no standalone page and no separate URL. This module computes the geometry
and hands `build_guests.py` a JSON payload to inject into the guest's wrapped.json.

Privacy model: every member of a group gets their own payload, embedded only in their own
wrapped.json. That payload contains ONLY photos that include the viewer (any combination
with other members, plus their best solo shots) — other members' pairings without the
viewer are not present in the payload at all.

Layout: a deterministic ego graph (issue #1) computed PER VIEWER — the viewer is the
canvas center, members fan out clockwise from 12 o'clock in strength order. No NetworkX,
no randomness: same members + weights => identical coordinates.
"""
import math

NODE_R = 30      # nominal member radius (used for ring spacing)
VIEWER_R = 44    # the viewer's node — largest, always centered
GAP = 20         # min gap between member nodes on a ring
LABEL_PAD = 60   # margin around the outer ring for labels (keeps 3/9 o'clock labels on-canvas)


def _pair_weights(edges):
    return {frozenset((a, b)): w for a, b, w in edges}


def _detect_couples(cids, names, wmap):
    """Mutual-best pairs among the ring members (each other's #1 tie) — kept adjacent.
    Mirrors the 'give couples a chance' pass in label_server.py /api/group_presets,
    but over the raw pair weights we already have for this group."""
    best = {}
    for a in cids:
        cand = [(wmap.get(frozenset((a, b)), 0), b) for b in cids if b != a]
        cand = [c for c in cand if c[0] > 0]
        if not cand:
            continue
        cand.sort(key=lambda t: (-t[0], names.get(t[1], "")))  # strongest tie, name asc tiebreak
        best[a] = cand[0][1]
    couples = {}
    for a, b in best.items():
        if best.get(b) == a:                                    # each other's #1 -> couple
            couples[a] = b
    return couples


def ego_layout(viewer_cid, members, edges):
    """Deterministic ego layout centered on the viewer.

    Returns (positions, W, H, rings, ringR):
      positions : {cid: (x, y)} for the default (wide) projection, viewer at center.
      rings     : list of rings, each a list of cids clockwise from 12 o'clock, strongest first.
      ringR     : ring radii (px).
    The JS reprojects `rings`/`ringR` responsively (upper-270 arc on narrow screens);
    `positions` is the canonical wide layout used for the determinism test / no-JS fallback.
    """
    names = {m["cid"]: (m.get("name") or m.get("first") or "") for m in members}
    cids = [m["cid"] for m in members if m["cid"] != viewer_cid]
    wmap = _pair_weights(edges)
    wv = {}                                                     # weight of each member's tie to the viewer
    for a, b, w in edges:
        if a == viewer_cid:
            wv[b] = w
        elif b == viewer_cid:
            wv[a] = w
    couple_of = _detect_couples(cids, names, wmap)
    # sort: photos-together-with-viewer desc, then name asc
    order = sorted(cids, key=lambda c: (-wv.get(c, 0), names.get(c, "")))
    placed, seq = set(), []
    for c in order:
        if c in placed:
            continue
        seq.append(c); placed.add(c)
        p = couple_of.get(c)                                   # keep detected couples adjacent
        if p is not None and p not in placed:
            seq.append(p); placed.add(p)

    if len(seq) <= 9:
        rings = [seq] if seq else []
    else:
        inner_n = 8                                            # top ~8 inner, rest outer
        if inner_n < len(seq) and couple_of.get(seq[inner_n - 1]) == seq[inner_n]:
            inner_n -= 1                                       # don't split a couple across rings
        if inner_n < 2:
            inner_n = 8
        rings = [seq[:inner_n], seq[inner_n:]]

    def ring_radius(n):
        if n <= 1:
            return 155.0
        return max(155.0, n * (2 * NODE_R + GAP) / (2 * math.pi))

    if len(rings) == 1:
        ringR = [ring_radius(len(rings[0]))]
    elif len(rings) == 2:
        ri = ring_radius(len(rings[0]))
        ro = max(ri + 2 * NODE_R + 40, ring_radius(len(rings[1])))
        ringR = [ri, ro]
    else:
        ringR = []

    Rmax = ringR[-1] if ringR else 155.0
    W = H = int(round(2 * (Rmax + NODE_R + LABEL_PAD)))
    cx = cy = W / 2.0
    positions = {viewer_cid: (round(cx, 1), round(cy, 1))}
    for ri, ring in enumerate(rings):
        R = ringR[ri]; n = len(ring) or 1
        rot = math.pi / n if ri == 1 else 0.0                  # offset outer ring between inner nodes
        for i, c in enumerate(ring):
            th = 2 * math.pi * i / n + rot                     # clockwise from 12 o'clock
            positions[c] = (round(cx + R * math.sin(th), 1), round(cy - R * math.cos(th), 1))
    return positions, W, H, rings, ringR


def member_map_payload(group_name, viewer_cid, members, photos_meta, edges):
    """The viewer-scoped map payload injected into wrapped.json as `groups[].map`.

    photos_meta MUST already be filtered to viewer-inclusive photos — this function does no
    filtering of its own. Geometry is recomputed per viewer here (CONTRACT B); any positions
    computed by the cheap `layout()` shim are irrelevant.

    Node radius encodes tie strength to the viewer; edge width encodes pair weight, both
    baked at build time so the client never re-derives the encoding (DESIGN.md § Guest ego
    graph). `rings`/`ringR` let the client reproject responsively; `W`/`H` are the canonical
    wide projection.
    """
    pos, W, H, rings, ringR = ego_layout(viewer_cid, members, edges)

    wv = {}                                                    # per-member tie weight -> node size cue
    for a, b, w in edges:
        if a == viewer_cid:
            wv[b] = w
        elif b == viewer_cid:
            wv[a] = w
    maxwv = max(list(wv.values()) + [1])
    mems = []
    for m in members:
        c = m["cid"]
        r = VIEWER_R if c == viewer_cid else round(26 + 10 * (wv.get(c, 0) / maxwv), 1)
        mems.append(dict(m, r=r))

    maxw = max((w for _, _, w in edges), default=1)
    lm = math.log1p(maxw) or 1
    return dict(name=group_name, me=viewer_cid, members=mems, photos=photos_meta,
                edges=[[a, b, w, round(1.5 + 3.5 * math.log1p(w) / lm, 1)] for a, b, w in edges],
                W=W, H=H, rings=rings, ringR=ringR, viewR=VIEWER_R)


# --------------------------------------------------------------------------------------
# Admin-only standalone page (label_server `/explore`). NOT a guest surface and never
# deployed: guests get the React map in-deck at `#/map`. This exists only so the local EDA
# tool keeps working. It renders a payload from `member_map_payload`, so the geometry and
# tie-strength encoding stay single-source — only the presentation is separate.
# --------------------------------------------------------------------------------------
def render_admin_explorer(payload, back_url, header_extra=""):
    """Standalone HTML for one viewer-scoped map payload. Admin/local only."""
    import html, json
    data = dict(payload, back=back_url)
    group_name = payload["name"]
    members = payload["members"]
    me = next((m for m in members if m["cid"] == payload["me"]),
              members[0] if members else {"first": "You"})
    first = me.get("first") or "You"
    eyebrow = html.escape(f"{group_name} · {len(members)} people")
    h1 = html.escape(f"{first}'s wedding graph")
    title = html.escape(f"{first}'s wedding graph — Preethi & Neel")

    doc = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=robots content="noindex,nofollow">
<title>__TITLE__</title>
<style>
:root{--bg:#221b18;--card:#2c231f;--ink:#f3ece1;--muted:#b3a08f;--gold:#e0a63a;--haldi:#f2c14e;--hairline:#3a2f28;--line:rgba(255,255,255,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:22px 20px 6px;max-width:1000px;margin:0 auto}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold)}
h1{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-weight:500;font-size:32px;margin:6px 0 2px}
.sub{color:var(--muted);font-size:14px}
a.back{color:var(--gold);font-size:13px;text-decoration:none}
main{max-width:1000px;margin:0 auto;padding:0 14px 60px}
svg{width:100%;height:auto;display:block;touch-action:manipulation}
.node{cursor:pointer}
.node circle.back{fill:var(--card)}
.node circle.ring{fill:none;stroke:#9c8568;stroke-width:2.5}
.node.me circle.ring{stroke:var(--haldi);stroke-width:4.5}
.node.sel circle.ring{stroke:var(--haldi);stroke-width:5}
.node:focus{outline:none}
.node:focus circle.ring{stroke:var(--haldi)}
.node:focus-visible circle.ring{stroke:var(--haldi);stroke-width:5}
.node text{font-size:12px;fill:var(--ink);text-anchor:middle;paint-order:stroke;stroke:var(--bg);stroke-width:3}
.node.me text{fill:var(--haldi)}
line{stroke:#8a7561;stroke-opacity:.85;stroke-linecap:round}line.hot{stroke:var(--haldi);stroke-opacity:.85}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 14px;min-height:44px}
.chip{display:flex;align-items:center;gap:6px;background:var(--card);border:1px solid var(--hairline);border-radius:20px;padding:3px 6px 3px 4px;font-size:13px}
.chip img{width:28px;height:28px;border-radius:50%;object-fit:cover}
.chip.fixed{border-color:var(--gold)}
.chip button.rm{min-width:28px;min-height:28px;display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:var(--haldi);font-weight:700;font-size:16px;line-height:1;cursor:pointer;padding:0;border-radius:50%}
.count{color:var(--muted);font-size:14px}button{font:inherit;font-size:13px;background:none;border:1px solid var(--hairline);color:var(--muted);border-radius:8px;padding:6px 12px;cursor:pointer}
#clr{min-width:44px;min-height:28px}
button:focus-visible,.chip button.rm:focus-visible{outline:2px solid var(--haldi);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px}
.grid figure{margin:0;border-radius:8px;overflow:hidden;background:#000;aspect-ratio:1;position:relative;cursor:zoom-in}
.grid figure:focus-visible{outline:2px solid var(--haldi);outline-offset:2px}
.grid img{width:100%;height:100%;object-fit:cover}
.grid figcaption{position:absolute;left:0;right:0;bottom:0;padding:14px 8px 6px;font-size:11px;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.75));opacity:0;transition:.15s}
.grid figure:hover figcaption,.grid figure:focus-visible figcaption{opacity:1}
#lb{position:fixed;inset:0;background:rgba(10,5,7,.95);display:none;align-items:center;justify-content:center;z-index:50;flex-direction:column}
#lb.on{display:flex}#lb img{max-width:96vw;max-height:88vh}#lb .cap{color:var(--muted);font-size:13px;margin-top:8px}
.hint{color:var(--muted);font-size:13px;margin:6px 0 16px}
</style></head><body>
<header><!--__EXTRA__--><a class=back id=back href="#">← your Wrapped</a><div class=eyebrow id=eyebrow style="margin-top:8px">__EYEBROW__</div><h1 id=gname>__H1__</h1>
<div class=sub>Every photo here includes you. Tap faces to build a combination.</div></header>
<main><svg id=map role="group" aria-label="wedding graph"></svg><div class=bar id=bar></div><div class=hint id=cnt aria-live="polite"></div><div class=grid id=grid></div></main>
<div id=lb tabindex="-1"><img id=lbi alt=""><div class=cap id=lbc></div></div>
<script>
const DATA=__DATA__;const $=i=>document.getElementById(i);let sel=[];let lastFocus=null;let opener=null;
const esc=s=>String(s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const NS='http://www.w3.org/2000/svg',el=(t,a)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e};
const by=Object.fromEntries(DATA.members.map(m=>[m.cid,m]));const me=by[DATA.me];
$('back').href=DATA.back+'#people';
$('map').setAttribute('aria-label',DATA.name+' — tap or press Enter on a face to filter photos');
let POS={};
function relayout(){const s=$('map');let W,H,cx,cy;
 const px=s.clientWidth||900;const narrow=px<560;
 const Rmax=DATA.ringR.length?DATA.ringR[DATA.ringR.length-1]:155;
 if(!narrow){W=DATA.W;H=DATA.H;cx=W/2;cy=H/2;
  DATA.rings.forEach((ring,ri)=>{const R=DATA.ringR[ri],n=ring.length||1,rot=ri===1?Math.PI/n:0;
   ring.forEach((c,i)=>{const th=2*Math.PI*i/n+rot;POS[c]=[cx+R*Math.sin(th),cy-R*Math.cos(th)];});});
 }else{W=2*(Rmax+DATA.viewR+44);H=2*(Rmax+DATA.viewR+70);cx=W/2;cy=H/2-6;
  const SPAN=Math.PI*1.5;                                   // upper 270 arc so 3/9 o'clock labels stay on-canvas at 390px
  DATA.rings.forEach((ring,ri)=>{const R=DATA.ringR[ri],n=ring.length||1;
   ring.forEach((c,i)=>{let th;
    if(n===1){th=0;}else{const half=Math.ceil((n-1)/2)||1;const step=(SPAN/2)/half;const k=Math.ceil(i/2);th=i===0?0:(i%2?1:-1)*k*step;}
    POS[c]=[cx+R*Math.sin(th),cy-R*Math.cos(th)];});});
 }
 POS[DATA.me]=[cx,cy];s.setAttribute('viewBox','0 0 '+W+' '+H);
}
function hitsAndCo(){const hits=DATA.photos.filter(p=>sel.every(cc=>p.mem.includes(cc)));
 const n={};hits.forEach(p=>p.mem.forEach(cc=>n[cc]=(n[cc]||0)+1));return {hits,n}}
function toggle(cid){lastFocus=cid;sel=sel.includes(cid)?sel.filter(x=>x!==cid):sel.concat([cid]);paint();}
function draw(counts){const s=$('map');s.innerHTML='';
 const act=[DATA.me].concat(sel);
 const visible=c=>c===DATA.me||sel.includes(c)||(counts[c]||0)>0;   // filter map to people reachable from the current combination
 DATA.edges.forEach(e=>{const a=POS[e[0]],b=POS[e[1]];if(!a||!b)return;
  if(!(visible(e[0])&&visible(e[1])))return;
  if(!(act.includes(e[0])||act.includes(e[1])))return;              // only edges touching you/your selection
  const hot=act.includes(e[0])&&act.includes(e[1]);
  s.appendChild(el('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],'stroke-width':hot?e[3]+1.5:e[3],class:hot?'hot':''}))});
 DATA.members.forEach(m=>{const isMe=m.cid===DATA.me;if(!visible(m.cid))return;
  const p=POS[m.cid];if(!p)return;const x=p[0],y=p[1],r=isMe?DATA.viewR:(m.r||28);
  const g=el('g',{class:'node'+(isMe?' me':'')+(sel.includes(m.cid)?' sel':''),'data-cid':m.cid});
  const cp=el('clipPath',{id:'c'+m.cid});cp.appendChild(el('circle',{cx:x,cy:y,r:r}));s.appendChild(cp);
  g.appendChild(el('circle',{class:'back',cx:x,cy:y,r:r+2}));
  g.appendChild(el('image',{href:m.face,x:x-r,y:y-r,width:2*r,height:2*r,'clip-path':'url(#c'+m.cid+')',preserveAspectRatio:'xMidYMid slice'}));
  g.appendChild(el('circle',{class:'ring',cx:x,cy:y,r:r+1}));
  const t=el('text',{x:x,y:y+r+15});t.textContent=isMe?'You':m.first;g.appendChild(t);
  if(!isMe&&counts[m.cid]){const t2=el('text',{x:x,y:y+r+29,style:'font-size:11px;fill:var(--muted)'});t2.textContent=counts[m.cid]+(sel.length?' together':' with you');g.appendChild(t2)}
  if(!isMe){g.setAttribute('tabindex','0');g.setAttribute('role','button');
   g.setAttribute('aria-pressed',sel.includes(m.cid)?'true':'false');
   g.setAttribute('aria-label',m.first+' — '+(counts[m.cid]||0)+' photos with you — toggle into combination');
   g.onclick=()=>toggle(m.cid);
   g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle(m.cid)}}}
  s.appendChild(g)});
 if(lastFocus!=null){const n=s.querySelector('[data-cid="'+lastFocus+'"]');if(n)n.focus()}
}
function paint(){const hc=hitsAndCo();draw(hc.n);
 $('bar').innerHTML='<div class="chip fixed"><img src="'+me.face+'" alt=""><b>You</b></div>'
  +sel.map(c=>'<div class=chip><img src="'+by[c].face+'" alt=""><b>'+esc(by[c].first)+'</b><button class="rm" data-x="'+c+'" aria-label="Remove '+esc(by[c].first)+' from combination">×</button></div>').join('')
  +(sel.length?'<button id=clr>clear</button>':'');
 document.querySelectorAll('.rm').forEach(x=>x.onclick=()=>{lastFocus=null;sel=sel.filter(c=>c!=+x.dataset.x);paint()});
 const clr=$('clr');if(clr)clr.onclick=()=>{lastFocus=null;sel=[];paint()};
 const hits=hc.hits;
 $('cnt').textContent=sel.length?hits.length+' photo'+(hits.length===1?'':'s')+' of you with '+sel.map(cc=>by[cc].first).join(' + ')
                                :'all '+hits.length+' photos of you with this group (including a few of just you)';
 $('grid').innerHTML=hits.map((p,i)=>{const cap=p.mem.filter(cc=>by[cc]).map(cc=>cc===DATA.me?'You':by[cc].first).join(', ');
   return '<figure tabindex="0" role="button" aria-label="'+esc('Photo with '+cap+' — open larger')+'" data-i="'+i+'"><img loading=lazy src="'+p.s+'" alt=""><figcaption>'+esc(cap)+'</figcaption></figure>'}).join('');
 document.querySelectorAll('.grid figure').forEach(f=>{const open=()=>{opener=f;const p=hits[+f.dataset.i];
    $('lbi').src=p.l||p.s;$('lbc').textContent=p.gallery+' — '+p.mem.filter(cc=>by[cc]).map(cc=>cc===DATA.me?'You':by[cc].first).join(', ');
    $('lb').classList.add('on');$('lb').focus()};
   f.onclick=open;f.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}}})}
function closeLb(){$('lb').classList.remove('on');if(opener){opener.focus();opener=null}}
$('lb').onclick=closeLb;
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('lb').classList.contains('on'))closeLb()});
window.addEventListener('resize',()=>{relayout();paint()});
relayout();paint();
</script></body></html>"""
    doc = (doc.replace("__TITLE__", title)
              .replace("__EYEBROW__", eyebrow)
              .replace("__H1__", h1)
              .replace("__DATA__", json.dumps(data))
              .replace("<!--__EXTRA__-->", header_extra))
    return doc


