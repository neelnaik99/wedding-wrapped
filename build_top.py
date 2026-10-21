"""Build Wrapped pages for the top-N clusters + a site/index.html to browse them.
Usage: python build_top.py [N | --min PHOTOS] [--force]   (default top 20; --min 50 = everyone with ≥50 photos; skips clusters in data/exclude.json; existing pages reused unless --force)
"""
import sys, json, subprocess, re
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent; D, SITE, APP = HERE / "data", HERE / "site", HERE / "app"
args = sys.argv[1:]; FORCE = "--force" in args; args = [a for a in args if a != "--force"]
MIN = int(args[args.index("--min") + 1]) if "--min" in args else None
N = int(args[0]) if args and "--min" not in args else None
labels = json.loads((D / "labels.json").read_text()) if (D / "labels.json").exists() else {}
exclude = set(json.loads((D / "exclude.json").read_text())) if (D / "exclude.json").exists() else set()
stats = pd.read_csv(D / "people_stats.csv", index_col=0)
top = [c for c in stats.index if c not in exclude and (MIN is None or stats.loc[c, "photos"] >= MIN)]
if N: top = top[:N]
print(f"{len(top)} people to build")

built = []
for cid in top:
    l = labels.get(str(cid), {})
    if l.get("status") in ("not_guest", "merged"): continue          # vendors/priest; fragments folded into their main cluster
    if l.get("guest_id") is not None and any(m.get("guest_id") == l["guest_id"] and int(k) != cid and int(k) in top[:top.index(cid)] for k, m in labels.items()): continue  # same guest already built under a bigger cluster
    name = l.get("first") or l.get("name") or f"Guest #{cid}"
    slug = re.sub(r"\W+", "-", (l.get("name") or name).lower()).strip("-")
    if FORCE or not (SITE / slug / "wrapped.json").exists():
        r = subprocess.run([str(HERE / ".venv/bin/python"), str(HERE / "build_wrapped.py"), "--cluster", str(cid), "--name", name, "--slug", slug],
                           capture_output=True, text=True)
        line = [l for l in r.stdout.splitlines() if "scenes" in l]
        print(f"#{cid:<5} {name:<14} {line[0] if line else r.stderr[-300:]}", flush=True)
    else:
        print(f"#{cid:<5} {name:<14} (exists)", flush=True)
    bundle = APP / "bundle.html"
    if bundle.exists(): (SITE / slug / "index.html").write_bytes(bundle.read_bytes())
    ctx = json.loads((SITE / slug / "wrapped.json").read_text())
    built.append(dict(cid=cid, name=name, slug=slug, n=ctx["n_photos"], events=ctx["n_events"], scenes=ctx["n_scenes"], hero=ctx["hero"].replace("../", "")))

cards = "".join(f"<a href='{b['slug']}/'><img src='{b['hero']}' loading=lazy><div><b>{b['name']}</b><small>#{b['cid']} · {b['n']} photos · {b['events']} events · {b['scenes']} moments</small></div></a>" for b in built)
(SITE / "index.html").write_text(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Wedding Wrapped — drafts</title>
<style>body{{background:#1a0f12;color:#f7efe6;font:15px system-ui;margin:0;padding:24px}}h1{{font:500 34px "Iowan Old Style",Palatino,Georgia,serif;margin:0 0 4px}}p{{color:#c9b3a6;margin:0 0 22px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px}}a{{color:inherit;text-decoration:none;background:#24151a;border-radius:10px;overflow:hidden;display:block}}
a img{{width:100%;aspect-ratio:4/5;object-fit:cover;display:block}}a div{{padding:10px 12px}}b{{display:block;font-family:Georgia,serif;font-size:18px}}small{{color:#c9b3a6}}</style>
<h1>Wedding Wrapped — drafts</h1><p>{len(built)} people{" with ≥" + str(MIN) + " photos" if MIN else " (top " + str(len(built)) + ")"} · names marked “Guest #” are unlabeled clusters · <a style="color:#e0a63a" href="relationship_graph.html">who-with-whom graph →</a></p><div class=g>{cards}</div>""")
print(f"\n{len(built)} pages → {SITE/'index.html'}")
