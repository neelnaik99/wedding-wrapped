#!/bin/zsh
# Usage: ./run_eda.sh SRC [SRC ...]     SRC = folder or glob of photo folders
#   e.g. ./run_eda.sh "~/Downloads/neilandpreethi-photo-download-*of26/*"
set -e
cd "$(dirname "$0")"
.venv/bin/python extract_faces.py "$@" 2>&1 | grep -v "^find model\|^set det\|Applied providers"
.venv/bin/python cluster_and_eda.py --top 150
open data/eda_report.html
