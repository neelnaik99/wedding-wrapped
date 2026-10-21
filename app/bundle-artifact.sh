#!/bin/bash
# Build the single-file deck bundle: app/bundle.html
#
# Guest decks are static folders on Cloudflare Pages with no asset pipeline — each one is
# `index.html` + `wrapped.json` and nothing else. So the Vite output has to collapse into ONE
# self-contained HTML file with the CSS and JS inlined, which is what this produces.
#
# `build_guests.py` copies the result into every deck folder. It is gitignored (a build
# artifact), which is exactly why it must be rebuilt from source before any build or deploy —
# a stale bundle ships decks whose wrapped.json carries payloads the renderer doesn't know
# about, and nothing downstream catches it.
#
#   ./app/bundle-artifact.sh   (then: build_guests.py, then deploy_site.sh)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

npx tsc -b tsconfig.app.json
npx vite build

python3 - <<'PY'
import re, pathlib
dist = pathlib.Path("dist")
html = (dist / "index.html").read_text()

def asset(match_attr, pattern):
    """Read the one dist asset the built index.html points at."""
    m = re.search(pattern, html)
    if not m:
        raise SystemExit(f"bundle-artifact: no {match_attr} found in dist/index.html")
    p = dist / m.group(1).lstrip("/")
    if not p.exists():
        raise SystemExit(f"bundle-artifact: {p} missing")
    return m.group(0), p.read_text()

js_tag,  js  = asset("script", r'<script type="module"[^>]*src="([^"]+)"[^>]*></script>')
css_tag, css = asset("stylesheet", r'<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>')

# `</script>` inside a string literal would close the tag early; the escape is inert in JS.
out = html.replace(css_tag, f"<style>{css}</style>") \
          .replace(js_tag, "<script type=\"module\">" + js.replace("</script>", "<\\/script>") + "</script>")

pathlib.Path("bundle.html").write_text(out)
print(f"bundle.html  {len(out)/1024:.0f} KB  (js {len(js)/1024:.0f} KB + css {len(css)/1024:.0f} KB inlined)")
PY

# Fail loudly rather than shipping a bundle that fetches assets that aren't there.
grep -q 'src="/assets/' bundle.html && { echo "FAIL: bundle.html still references external assets" >&2; exit 1; }
echo "OK: app/bundle.html is self-contained"
