#!/bin/zsh
# Deploy the guest site to Cloudflare Pages, with safety checks first.
# One-time setup: npx wrangler login   (browser flow)
# Usage: ./deploy_site.sh [project-name] [branch]   (default: wedding-wrapped, production; e.g. "" preview)
set -e
cd "$(dirname "$0")"
SITE=site_guest; PROJECT="${1:-wedding-wrapped}"; BRANCH="${2:-}"

[ -f "$SITE/index.html" ] || { echo "FAIL: no landing page"; exit 1; }
grep -q '/api/login' "$SITE/index.html" || { echo "FAIL: root is not the Login page (admin bundle at root?)"; exit 1; }
# Login: the email→Link map is bundled into functions/, and must never be a public file.
[ -f functions/_lib/login-map.json ] || { echo "FAIL: no login map — run make_emails.py"; exit 1; }
find "$SITE" -name 'login-map.json' | grep -q . && { echo "FAIL: login-map.json inside $SITE would be public"; exit 1; }
# Every Link in the map must be absolute and exist in this build — a map left over from before a
# rebuild can point at a deleted Hub, and a relative href is unopenable in an email.
python3 - "$SITE" <<'PY' || { echo "FAIL: login map has Links that are relative or not in $SITE — rerun make_emails.py --base-url ..."; exit 1; }
import json, sys
from pathlib import Path
from urllib.parse import urlparse
site = Path(sys.argv[1]); bad = []
for e in json.load(open("functions/_lib/login-map.json")).values():
    u = urlparse(e["url"])
    if u.scheme != "https" or not (site / u.path.strip("/") / "index.html").is_file():
        bad.append(e["url"])
for b in bad[:5]: print("  dead:", b)
sys.exit(1 if bad else 0)
PY
grep -q 'REPLACE_WITH_LOGIN_KV_ID' wrangler.toml && { echo "FAIL: set the LOGIN_KV id in wrangler.toml (npx wrangler kv namespace create LOGIN_KV)"; exit 1; }
grep -qs '"draft": true' "$SITE"/*/wrapped.json && { echo "FAIL: a deck still has draft:true"; exit 1; }
grep -rls "guest_id\|@gmail\|@yahoo" "$SITE"/*/wrapped.json "$SITE"/*/pool.json(N) | head -1 | grep -q . && { echo "FAIL: PII in wrapped.json/pool.json"; exit 1; }
# Household Decks (h/<token>/) carry names, photos and links only. They live one level deeper
# than a deck, so the glob above cannot see them — without this a regression there would ship an
# address silently. index.html files identical to the app bundle are skipped: the bundle's admin
# code names the guest_id field; every other page and data file under h/ is checked.
H_FILES=("$SITE"/h/*/*.json(N))
for f in "$SITE"/h/*/index.html(N); do cmp -s "$f" app/bundle.html || H_FILES+=("$f"); done
(( ${#H_FILES} )) && grep -lsE "guest_id|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}" "${H_FILES[@]}" | head -1 | grep -q . && { echo "FAIL: PII in a Household Deck"; exit 1; }
# The photo rule (docs/adr/0002) and the no-personal-link rule, re-run from what is on disk: a
# failed build can leave violators behind, and build_guests' own check never sees them then.
PY="${WW_PYTHON:-.venv/bin/python}"; [ -x "$PY" ] || PY=python3
"$PY" photo_rule.py --check "$SITE" || { echo "FAIL: photo rule / personal-link check failed in $SITE/h"; exit 1; }
N=$(find "$SITE" -type f | wc -l | tr -d ' ')
[ "$N" -lt 20000 ] || { echo "FAIL: $N files >= Cloudflare Pages 20k limit"; exit 1; }
BIG=$(find "$SITE" -type f -size +20M | wc -l | tr -d ' ')
[ "$BIG" -eq 0 ] || { echo "FAIL: $BIG files over 20MB"; exit 1; }
echo "checks passed: $N files, $(du -sh $SITE | cut -f1)"
npx wrangler pages deploy "$SITE" --project-name "$PROJECT" --commit-dirty=true ${BRANCH:+--branch=$BRANCH}
