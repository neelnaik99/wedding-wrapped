#!/usr/bin/env python3
"""Join telemetry events against build-time pool zones (issue #39's calibration read).

Usage:  .venv/bin/python analyze_events.py events.json
        events.json = the Supabase export: select * from events (service key, local only).
Prints net selection-rate by zone over guests who logged at least one event.
Family decks (photo counts above FAMILY_EXCLUDE_MIN_PHOTOS) are excluded per #39.
"""
import json, sys
from pathlib import Path

FAMILY_EXCLUDE_MIN_PHOTOS = 300   # decks above this are family-scale; excluded from calibration

def load_pools(site=Path("site_guest"), manifest=Path("data/send_manifest.json")):
    """slug -> {photo_id -> zone}, skipping family-scale decks."""
    pools = {}
    for m in json.loads(manifest.read_text()):
        if m.get("n_photos", 0) > FAMILY_EXCLUDE_MIN_PHOTOS: continue
        pf = site / m["token"] / "pool.json"
        if not pf.exists(): continue
        pools[m["token"]] = {p["url"].split("/img/l/")[-1]: p["zone"]
                             for p in json.loads(pf.read_text())["photos"]}
    return pools

def zone_rates(events, pools):
    """zone -> (net-selected count, zone size across guests with >=1 event).

    env=None is treated as prod (rows always carry env; be liberal in what we accept);
    stage rows never count. Net selection per (slug, photo): last select_on/off wins.
    """
    prod = [e for e in events if e.get("env") == "prod" or e.get("env") is None]
    net, active = {}, set()
    for e in sorted(prod, key=lambda e: e.get("ts", "")):
        slug = e.get("slug")
        if slug not in pools: continue
        active.add(slug)
        if e.get("action") == "select_on": net[(slug, e.get("photo"))] = True
        elif e.get("action") == "select_off": net[(slug, e.get("photo"))] = False
    if not active: return {}
    rates = {}
    for slug in active:
        for photo, zone in pools[slug].items():
            sel, tot = rates.get(zone, (0, 0))
            rates[zone] = (sel + (1 if net.get((slug, photo)) else 0), tot + 1)
    return rates

if __name__ == "__main__":
    events = json.loads(Path(sys.argv[1]).read_text())
    rates = zone_rates(events, load_pools())
    for zone in ("shown", "skipped", "below_bar"):
        sel, tot = rates.get(zone, (0, 0))
        pct = f"{100*sel/tot:.1f}%" if tot else "—"
        print(f"{zone:10} {sel:4}/{tot:<5} selected  ({pct})")
