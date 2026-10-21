"""
Cameo-tier postcard page (issue #32 / DESIGN.md § Experience tiers; mocks CameoWeb / CameoMobile).

A cameo guest (15-49 photos) gets a static postcard instead of the full React deck: the same
7-beat spine at minimum size, warmth-first. It renders from the guest's wrapped.json payload
(embedded inline, no fetch) so it is fully self-contained on Cloudflare Pages:
  cover (name + best photo hero) -> "You & the couple" strip -> full selectable grid -> download bar.

Same night chrome as the explorer, same guest_accent/accent_ink tokens the deck uses, same
token/visibility pipeline (the grid is exactly out['gallery'], already visibility-filtered by
build_wrapped's curated path). Selection is the shared gesture (whole tile = hit target, 24px
check chip = visual state only, aria-pressed + aria-live count). "Download all" excludes
courtesy-flagged third-party photos by default; a store-only client zip bundles the picks.

Voice: favorites-framed ("our favorite photos of you"), never "kept the good stuff", no clock,
nothing that reveals the grading (DESIGN.md Voice).
"""
import html as _html
import json
from pathlib import Path

# night chrome tokens (DESIGN.md frontmatter)
NIGHT_CANVAS, NIGHT_CARD, NIGHT_TILE = "#221b18", "#2c231f", "#382d26"
NIGHT_INK, NIGHT_MUTED, NIGHT_HAIRLINE, NIGHT_RING = "#f3ece1", "#b3a08f", "#3a2f28", "#9c8568"


def _payload(out):
    """Flatten the visibility-filtered gallery into the postcard's photo list."""
    photos = []
    for g in out.get("gallery", []):
        for s in g.get("shots", []):
            photos.append(dict(id=s.get("id"), s=s.get("s") or s.get("url"), l=s.get("url"),
                               event=s.get("event", ""), bucket=s.get("bucket", ""),
                               courtesy=bool(s.get("courtesy", False))))
    return photos


def render_postcard(out):
    first = out.get("name") or "friend"
    photos = _payload(out)
    couple = [p for p in photos if p["bucket"] == "with_couple"][:3]
    events = [e["name"] for e in out.get("events", [])]
    span = ""
    if len(events) >= 2:
        span = f" from the {events[0]} to the {events[-1]}"
    elif events:
        span = f" from the {events[0]}"
    accent = out.get("guest_accent", "#e8b45a")
    accent_ink = out.get("accent_ink", "#221b18")
    n_all = sum(1 for p in photos if not p["courtesy"])   # "Download all" default set (courtesy excluded)

    data = dict(first=first, couple=out.get("couple", "Preethi & Neel"), photos=photos,
                accent=accent, accent_ink=accent_ink, n_all=n_all,
                zipname=f"{out.get('couple','Preethi & Neel').replace(' & ','-').replace(' ','-')}-{first}-photos".replace("--", "-"))


    hero_cap = _html.escape(("Your best shot · " + out["hero_event"]) if out.get("hero_event") else "Your best shot")
    hero_url = _html.escape(out.get("hero", ""))
    dates = _html.escape(out.get("dates", ""))
    couple_name = _html.escape(out.get("couple", "Preethi & Neel"))
    ehead = _html.escape(first)

    couple_strip = ""
    if couple:
        cells = "".join(
            f'<figure class=cf><img loading=lazy src="{_html.escape(c["s"])}" alt="">'
            f'<figcaption>{_html.escape(c["event"])}</figcaption></figure>' for c in couple)
        couple_strip = (
            f'<section class=block><div class=eyebrow>You &amp; the couple</div>'
            f'<div class=cstrip>{cells}</div></section>')

    return _TEMPLATE \
        .replace("__NAME__", ehead) \
        .replace("__COUPLE__", couple_name) \
        .replace("__DATES__", dates) \
        .replace("__SPAN__", _html.escape(span)) \
        .replace("__HERO__", hero_url) \
        .replace("__HEROCAP__", hero_cap) \
        .replace("__COUPLESTRIP__", couple_strip) \
        .replace("__ACCENT__", accent) \
        .replace("__ACCENT_INK__", accent_ink) \
        .replace("__NIGHT_CANVAS__", NIGHT_CANVAS).replace("__NIGHT_CARD__", NIGHT_CARD) \
        .replace("__NIGHT_TILE__", NIGHT_TILE).replace("__NIGHT_INK__", NIGHT_INK) \
        .replace("__NIGHT_MUTED__", NIGHT_MUTED).replace("__NIGHT_HAIRLINE__", NIGHT_HAIRLINE) \
        .replace("__NIGHT_RING__", NIGHT_RING) \
        .replace("__DATA__", json.dumps(data))


def build_postcard(out_dir, out):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render_postcard(out))


_TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=robots content="noindex,nofollow">
<title>__NAME__ — __COUPLE__</title>
<style>
:root{--bg:__NIGHT_CANVAS__;--card:__NIGHT_CARD__;--tile:__NIGHT_TILE__;--ink:__NIGHT_INK__;--muted:__NIGHT_MUTED__;--hair:__NIGHT_HAIRLINE__;--ring:__NIGHT_RING__;--accent:__ACCENT__;--accent-ink:__ACCENT_INK__}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding-bottom:88px}
.serif{font-family:"Fraunces","Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
.eyebrow{font-family:"Geist Mono",ui-monospace,"SF Mono",Menlo,monospace;text-transform:uppercase;font-size:12px;letter-spacing:1.6px;color:var(--accent)}
.wrap{max-width:1100px;margin:0 auto;padding:0 20px}
.cover{display:flex;gap:40px;padding:56px 0 40px;align-items:center;flex-wrap:wrap}
.hero{width:min(420px,100%);aspect-ratio:4/5;border-radius:24px;background:var(--card) center/cover no-repeat;position:relative;flex-shrink:0}
.hero .cap{position:absolute;bottom:14px;left:16px;font-family:"Geist Mono",ui-monospace,Menlo,monospace;text-transform:uppercase;font-size:11px;letter-spacing:.8px;color:var(--ink);text-shadow:0 1px 3px rgba(0,0,0,.7)}
.cover .col{flex:1;min-width:260px;display:flex;flex-direction:column;gap:14px}
h1{margin:0;font-weight:450;font-size:clamp(34px,5vw,56px);line-height:1.06;letter-spacing:-.6px}
.lede{font-size:17px;line-height:1.5;max-width:42ch;color:var(--ink)}
.block{padding:0 0 36px}
.cstrip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}
.cf{margin:0;aspect-ratio:4/3;border-radius:10px;overflow:hidden;background:var(--tile);position:relative}
.cf img{width:100%;height:100%;object-fit:cover;display:block}
.cf figcaption{position:absolute;left:0;right:0;bottom:0;padding:16px 10px 8px;font-family:"Geist Mono",Menlo,monospace;text-transform:uppercase;font-size:11px;letter-spacing:.8px;color:var(--ink);background:linear-gradient(transparent,rgba(0,0,0,.72))}
.ghead{display:flex;align-items:baseline;gap:12px;margin-bottom:12px}
.ghead .hint{font-size:13px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.cell{margin:0;aspect-ratio:1;border-radius:10px;overflow:hidden;background:var(--tile);position:relative;cursor:pointer;border:0;padding:0;width:100%;font:inherit;color:inherit}
.cell img{width:100%;height:100%;object-fit:cover;display:block}
.cell .chip{position:absolute;top:8px;right:8px;width:24px;height:24px;border-radius:50%;border:2px solid var(--ring);background:rgba(20,15,12,.35);display:flex;align-items:center;justify-content:center}
.cell .chip svg{display:none}
.cell[aria-pressed=true] .chip{background:var(--accent);border-color:var(--accent)}
.cell[aria-pressed=true] .chip svg{display:block;stroke:var(--accent-ink)}
.cell .ev{position:absolute;left:0;right:0;bottom:0;padding:14px 8px 6px;font-family:"Geist Mono",Menlo,monospace;text-transform:uppercase;font-size:11px;letter-spacing:.6px;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.72));opacity:0;transition:.15s}
.cell:hover .ev,.cell:focus-visible .ev{opacity:1}
.cell:focus-visible{outline:none}.cell:focus-visible .chip{box-shadow:0 0 0 2px var(--bg),0 0 0 4px var(--accent)}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--hair);padding:12px 20px;display:flex;align-items:center;gap:12px;z-index:20}
.bar .count{font-size:13px;color:var(--muted)}
.bar .btns{margin-left:auto;display:flex;gap:10px}
.btn{border-radius:50px;font-weight:560;font-size:15px;padding:11px 22px;cursor:pointer;border:1px solid var(--ring);background:none;color:var(--ink);font-family:inherit}
.btn.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.btn[hidden]{display:none}
.btn:disabled{opacity:.5;cursor:default}
@media(max-width:560px){.cover{padding:32px 0 24px;gap:20px}.grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.btn{padding:10px 16px;font-size:13px}}
</style></head><body>
<div class=wrap>
  <section class=cover>
    <div class=hero id=hero style="background-image:url('__HERO__')"><span class=cap>__HEROCAP__</span></div>
    <div class=col>
      <div class=eyebrow>__COUPLE__ · __DATES__</div>
      <h1 class=serif>__NAME__, we&rsquo;re so glad you came.</h1>
      <div class=lede>Here are our favorite photos of you__SPAN__ — yours to take.</div>
    </div>
  </section>
  __COUPLESTRIP__
  <section class=block>
    <div class=ghead><div class=eyebrow>All your photos</div><div class=hint>tap to select — take the ones you love</div></div>
    <div class=grid id=grid role=list></div>
  </section>
</div>
<div class=bar role=region aria-label="Download">
  <div class=count id=count aria-live=polite>Tap photos to choose, or take them all</div>
  <div class=btns>
    <button class=btn id=all type=button></button>
    <button class="btn primary" id=some type=button hidden></button>
  </div>
</div>
<script>
const DATA=__DATA__;const $=i=>document.getElementById(i);
const sel=new Set();
const CRCT=(()=>{const t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1);t[n]=c;}return t;})();
function crc32(u8){let c=~0;for(let i=0;i<u8.length;i++)c=CRCT[(c^u8[i])&0xff]^(c>>>8);return (~c)>>>0;}
async function storeZip(files){const enc=new TextEncoder();const parts=[],central=[];let off=0;
 for(const f of files){const data=new Uint8Array(await f.blob.arrayBuffer());const name=enc.encode(f.name);const crc=crc32(data);
  const lf=new DataView(new ArrayBuffer(30));lf.setUint32(0,0x04034b50,true);lf.setUint16(4,20,true);lf.setUint32(14,crc,true);
  lf.setUint32(18,data.length,true);lf.setUint32(22,data.length,true);lf.setUint16(26,name.length,true);
  parts.push(new Uint8Array(lf.buffer),name,data);
  const ch=new DataView(new ArrayBuffer(46));ch.setUint32(0,0x02014b50,true);ch.setUint16(4,20,true);ch.setUint16(6,20,true);
  ch.setUint32(16,crc,true);ch.setUint32(20,data.length,true);ch.setUint32(24,data.length,true);ch.setUint16(28,name.length,true);ch.setUint32(42,off,true);
  central.push({h:new Uint8Array(ch.buffer),name});off+=30+name.length+data.length;}
 const cstart=off;let clen=0;for(const c of central){parts.push(c.h,c.name);clen+=46+c.name.length;}
 const e=new DataView(new ArrayBuffer(22));e.setUint32(0,0x06054b50,true);e.setUint16(8,central.length,true);e.setUint16(10,central.length,true);
 e.setUint32(12,clen,true);e.setUint32(16,cstart,true);parts.push(new Uint8Array(e.buffer));
 return new Blob(parts,{type:'application/zip'});}
function fname(p,used){let base=(p.event?p.event.replace(/[^A-Za-z0-9]+/g,'-')+'-':'')+p.id.split('/').pop();
 let n=base,i=1;while(used.has(n)){n=base.replace(/(\\.[^.]+)$/,'-'+(i++)+'$1');}used.add(n);return n;}
async function download(list,zipbase){
 if(!list.length)return;
 const b=$('all'),s=$('some');const lbl0=b.textContent,lbl1=s.textContent;b.disabled=s.disabled=true;
 try{
  if(list.length===1){const r=await fetch(list[0].l);const blob=await r.blob();
   trigger(blob,fname(list[0],new Set()));}
  else{const used=new Set();const files=[];
   for(const p of list){const r=await fetch(p.l);files.push({name:fname(p,used),blob:await r.blob()});}
   trigger(await storeZip(files),zipbase+'.zip');}
 }catch(e){$('count').textContent='Download failed — try again';}
 b.disabled=s.disabled=false;b.textContent=lbl0;s.textContent=lbl1;}
function trigger(blob,name){const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=name;
 document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),4000);}
function paint(){const k=sel.size;
 $('count').textContent=k?(k+' selected'):'Tap photos to choose, or take them all';
 $('all').textContent='Download all '+DATA.n_all;
 const s=$('some');if(k){s.hidden=false;s.textContent='Download '+k;s.setAttribute('aria-label','Download '+k);}else{s.hidden=true;}
 document.querySelectorAll('.cell').forEach(c=>c.setAttribute('aria-pressed',sel.has(c.dataset.id)?'true':'false'));}
function toggle(id){sel.has(id)?sel.delete(id):sel.add(id);paint();}
const CHECK='<svg width=13 height=13 viewBox="0 0 16 16" fill=none stroke-width=2.5><path d="M3 8.5l3.5 3.5L13 4.5"></path></svg>';
$('grid').innerHTML=DATA.photos.map(p=>
 '<button class=cell role=listitem type=button aria-pressed=false data-id="'+p.id+'" '
 +'aria-label="'+(p.event?p.event+' photo':'photo')+' — tap to select for download">'
 +'<img loading=lazy src="'+p.s+'" alt="">'
 +'<span class=ev>'+(p.event||'')+'</span>'
 +'<span class=chip>'+CHECK+'</span></button>').join('');
const byId=Object.fromEntries(DATA.photos.map(p=>[p.id,p]));
document.querySelectorAll('.cell').forEach(c=>{
 c.addEventListener('click',()=>toggle(c.dataset.id));
 c.addEventListener('keydown',e=>{if(e.key===' '||e.key==='Spacebar'){e.preventDefault();toggle(c.dataset.id);}});});
$('all').addEventListener('click',()=>download(DATA.photos.filter(p=>!p.courtesy),DATA.zipname+'-all'));
$('some').addEventListener('click',()=>download([...sel].map(id=>byId[id]),DATA.zipname));
paint();
</script></body></html>"""
