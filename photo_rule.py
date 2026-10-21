"""The photo rule (docs/adr/0002-one-deck-per-household.md).

A photo may be shown to a Household only if it includes at least one member of
that Household, or contains ONLY the couple (Preethi and Neel).
"""
import copy
import json
import re
from pathlib import Path

PHOTO_URL = re.compile(r'img/[ls]/([^"/]+/[^"/]+\.jpg)')
SITE_FACE = re.compile(r'^(?:\.\./)*img/face_(\d+)\.jpg$')   # one site-wide crop of a person
DECK_FACE = re.compile(r'^faces/(\d+)\.jpg$')                # this Household's own crop


def allowed(photo_cids, household, couple):
    return bool(photo_cids & household) or (bool(photo_cids) and photo_cids <= couple)


def _pid(url):
    m = PHOTO_URL.search(url) if isinstance(url, str) else None
    return m.group(1) if m else None


def strip_wrapped(w, by_photo, household, couple):
    """Copy of `w` without disallowed photos, plus how many were removed.

    Counts removals from gallery shots, picks and map photos; a replaced hero
    is not counted. Hero becomes the first allowed gallery shot (None if none).
    """
    w = copy.deepcopy(w)
    removed = 0

    def ok(url):
        # Fail closed: any reference we cannot parse into a photo id is dropped.
        pid = _pid(url)
        return pid is not None and allowed(by_photo.get(pid, set()), household, couple)

    for g in w.get("gallery") or []:
        shots = g.get("shots") or []
        keep = [s for s in shots if ok(s.get("url") if isinstance(s, dict) else None)]
        removed += len(shots) - len(keep)
        for s in keep:
            if "thumbs" in s:
                s["thumbs"] = [t for t in s["thumbs"] or [] if ok(t)]
        g["shots"] = keep

    picks = w.get("picks") or []
    w["picks"] = [p for p in picks if ok(p)]
    removed += len(picks) - len(w["picks"])

    for grp in w.get("groups") or []:
        m = grp.get("map")
        if m and "photos" in m:
            photos = m["photos"] or []
            keep = [p for p in photos
                    if isinstance(p, dict) and ok(p.get("l") or p.get("s"))]
            removed += len(photos) - len(keep)
            m["photos"] = keep

    # hero None means "no reference"; anything else must pass the rule.
    if w.get("hero") is not None and not ok(w["hero"]):
        w["hero"] = next((s["url"] for g in w.get("gallery") or []
                          for s in g.get("shots") or []), None)
    return w, removed


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def _face_problems(d, hh, household, couple, by_photo):
    """Face references in one Deck that break the face rule: a non-member face shown on a Deck
    must be this Household's crop (faces/<cid>.jpg, present, with a face_src photo that includes
    a member); a site-wide img/face_<cid>.jpg is only for members and the couple."""
    src = hh.get("face_src") or {} if isinstance(hh, dict) else {}
    out = []
    for text in sorted(set(_strings(hh))):
        if "face_" not in text and "faces/" not in text:
            continue
        m = SITE_FACE.match(text)
        if m and (int(m.group(1)) in household or int(m.group(1)) in couple):
            continue
        m = DECK_FACE.match(text)
        if m:
            pid = src.get(m.group(1))
            if pid and (d / text).is_file() and by_photo.get(pid, set()) & household:
                continue
            out.append(f"face {text} has no crop from a photo with a member")
        else:
            out.append(f"face {text} is not this Household's crop")
    return out


def violations(site, by_photo, households, couple):
    """Every disallowed photo reference in site/h/<token>/*.json (pool files
    included) and every face reference that breaks the face rule (_face_problems),
    plus token directories that are unknown or missing."""
    root = Path(site) / "h"
    out = []
    if root.is_dir():
        out += [f"{d.name}: unknown household"
                for d in sorted(root.iterdir())
                if d.is_dir() and d.name not in households]
    for token, household in households.items():
        d = root / token
        if not d.is_dir():
            out.append(f"{token}: missing")
            continue
        for f in sorted(d.glob("*.json")):
            seen = set()
            doc = json.loads(f.read_text())
            out += [f"{token}: {p}" for p in _face_problems(d, doc, household, couple, by_photo)]
            for text in _strings(doc):
                for pid in PHOTO_URL.findall(text):
                    if pid in seen:
                        continue
                    seen.add(pid)
                    if not allowed(by_photo.get(pid, set()), household, couple):
                        out.append(f"{token}: {pid}")
    return out


def leaked_tokens(site, person_tokens):
    """Per-person deck tokens found in any json/html file under site/h/<token>/ (all publicly
    fetchable: household.json, pool-<cid>.json, index.html): `<hh>: <token>`, once per Household."""
    out = []
    root = Path(site) / "h"
    for d in sorted(p for p in root.glob("*") if p.is_dir()):
        text = "\n".join(f.read_text(errors="replace") for f in sorted(d.rglob("*"))
                       if f.is_file() and f.suffix in (".json", ".html"))
        out += [f"{d.name}: {t}" for t in sorted(person_tokens) if t in text]
    return out


def check(site, data="data"):
    """Re-run the Household guards from what is on disk (the deploy check). Returns problem strings.

    Needs data/household_guard.json (written by build_guests: {couple, households: {token: [cids]}}),
    data/photo_people.parquet. The guard carries the person-token set and a build_id that must equal
    site/h/.build_id: a guard from another build (or none) is a failure, never a pass."""
    import pandas as pd
    data = Path(data)
    try:
        guard = json.loads((data / "household_guard.json").read_text())
        pp = pd.read_parquet(data / "photo_people.parquet")
    except (OSError, ValueError) as e:
        return [f"cannot run the check ({e}) - rebuild with build_guests.py"]
    try:
        site_id = (Path(site) / "h" / ".build_id").read_text().strip()
    except OSError:
        site_id = None
    if not guard.get("build_id") or guard["build_id"] != site_id:
        return [f"guard is from a different build than {site} (guard build_id {guard.get('build_id')!r}, "
                f"site {site_id!r}) - rerun build_guests.py"]
    by_photo = {pid: set(int(c) for c in cs) for pid, cs in pp.groupby("photo_id").cluster_id}
    households = {t: set(c) for t, c in guard["households"].items()}
    bad = violations(site, by_photo, households, set(guard["couple"]))
    return bad + leaked_tokens(site, set(guard["person_tokens"]))


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="Photo rule + token-leak check over a built site.")
    ap.add_argument("--check", metavar="SITE", required=True)
    ap.add_argument("--data", default="data")
    a = ap.parse_args()
    problems = check(a.check, a.data)
    for p in problems[:10]:
        print("  VIOLATION", p)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
