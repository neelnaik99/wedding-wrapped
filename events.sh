#!/bin/zsh
# Telemetry viewer (issue #39). Local-only: uses the service key.
# Usage: ./events.sh              -> recent sessions, one line each
#        ./events.sh <session>    -> that session's events, oldest first (id prefix is enough)
#        ./events.sh raw [limit]  -> old behavior: flat tail, newest first
set -e
cd "$(dirname "$0")"
KEY=$(npx supabase projects api-keys --project-ref <your-project-ref> --output json 2>/dev/null | python3 -c "
import json, sys
print(next(k['api_key'] for k in json.load(sys.stdin) if k.get('name') == 'service_role'))")
BASE="https://<your-project-ref>.supabase.co/rest/v1/events"

fetch() { curl -s "$BASE?$1" -H "apikey: $KEY" -H "Authorization: Bearer $KEY"; }

if [ "$1" = "raw" ]; then
  fetch "select=slug,session,device,photo,action,surface,env,ts&order=ts.desc&limit=${2:-20}" | python3 -m json.tool
elif [ -n "$1" ]; then
  fetch "select=session,slug,device,photo,action,surface,env,ts&session=like.$1*&order=ts.asc" | python3 -c "
import json, sys
rows = json.load(sys.stdin)
if not rows: sys.exit('no events for session prefix: $1')
r0 = rows[0]
print(f\"session {r0['session']}  slug={r0['slug']}  device={r0.get('device') or '?'}  env={r0['env']}  ({len(rows)} events)\")
for r in rows:
    photo = f\"  {r['photo']}\" if r.get('photo') else ''
    print(f\"  {r['ts'][11:19]}  {r['action']:20} [{r.get('surface') or '-'}]{photo}\")
"
else
  fetch "select=session,slug,device,env,action,ts&order=ts.desc&limit=400" | python3 -c "
import json, sys
rows = json.load(sys.stdin)
seen = {}
for r in rows:
    s = r.get('session') or '(pre-session rows)'
    d = seen.setdefault(s, {'slug': r['slug'], 'device': r.get('device'), 'env': r['env'], 'n': 0, 'last': r['ts'], 'first': r['ts']})
    d['n'] += 1; d['first'] = r['ts']
print(f'{len(seen)} sessions in the last {len(rows)} events — ./events.sh <id-prefix> for one:')
for s, d in seen.items():
    print(f\"  {s[:8]:10} {d['slug']:12} {d.get('device') or '?':8} {d['env']:5} {d['n']:3} events  {d['first'][5:16]} -> {d['last'][11:16]}\")
"
fi
