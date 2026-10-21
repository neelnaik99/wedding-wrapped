#!/bin/bash
# Copy the built Wedding Wrapped bundle into every guest folder that has a wrapped.json.
# Usage: ./deploy_bundle.sh   (run after `bash .../bundle-artifact.sh` inside app/)
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$ROOT/app/bundle.html"
if [ ! -f "$BUNDLE" ]; then
  echo "❌ $BUNDLE not found — build it first (bundle-artifact.sh inside app/)" >&2
  exit 1
fi
n=0
for d in "$ROOT"/site/*/; do
  if [ -f "$d/wrapped.json" ]; then
    cp "$BUNDLE" "$d/index.html"
    n=$((n+1))
    echo "  → ${d#$ROOT/}index.html"
  fi
done
echo "✅ Deployed bundle ($(du -h "$BUNDLE" | cut -f1)) to $n folder(s)."
