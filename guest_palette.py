"""
Derive per-guest accent tokens from that guest's own photos (issue #31).

Contract: DESIGN.md § Colors "Derived tokens" + "Derivation rules". For each guest we
sample their top ~30 role=focus photos, median-cut quantize (PIL), drop grey/dark/blown
colors, weight the rest by count and saturation, merge neighbouring hues, take the top two
hues >=60 apart, and clamp lightness into a contrast-safe band. The ink that sits on the
accent (share-card ground, tinted numerals, CTA fills) is chosen by *measured* contrast —
whichever of ink #1c1917 / night-ink #f3ece1 scores higher against the rendered accent —
and we assert the winner clears 4.5:1 (DESIGN.md's pick-by-contrast rule, issue #23).

Deterministic: same photos in -> same tokens out. No randomness, no timestamps. The runtime
never computes colour; tokens are written into wrapped.json at build time.

Public API (called by build_wrapped.build / build_guests.py):
    build_tokens(cid, pp_df, my_ids, cache_dir=CACHE, override=None) -> dict
        {"guest_accent": "#rrggbb", "guest_support": "#rrggbb", "accent_ink": "#rrggbb"}
    load_overrides() -> {cid_str: {"accent": .., "support": .., "ink": ..}}   (veto pattern)
"""
import colorsys, json, math
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
CACHE = HERE / "cache"
D = HERE / "data"
OVERRIDE_FILE = D / "palette_override.json"   # optional per-guest veto (same pattern as tier_override); not required to exist

# Fixed chrome inks (DESIGN.md frontmatter). Ink is picked by contrast between these two.
INK = "#1c1917"          # dark ink (light-block use)
NIGHT_INK = "#f3ece1"    # light ink (inverse use)
# Fallback pair when extraction finds nothing above saturation 0.25 (DESIGN.md fallback rule).
FALLBACK_ACCENT = "#c98a1e"    # accent-marigold
FALLBACK_SUPPORT = "#26365c"   # block-sangeet  (never block-grehshanti — too close to semantic-warn)

SAT_DROP = 0.22          # drop colours below this HSV saturation (greys)
VAL_LO, VAL_HI = 0.14, 0.97   # drop shadows / blowouts
SAT_FLOOR = 0.25         # if nothing beats this, use the fallback pair
SAT_CAP = 0.72           # clamp accent saturation so a surface colour stays legible
MIN_CONTRAST = 4.5       # WCAG AA for the accent vs its chosen ink
HUE_BIN = 30             # degrees; merge neighbouring hues
HUE_GAP = 60             # degrees; the two chosen hues must be at least this far apart
N_PHOTOS = 30            # sample budget per guest


# ---- colour math (self-contained; mirrors the snippet in issues #19/#23) ----
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def rel_lum(rgb):
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

def contrast(rgb1, rgb2):
    l1, l2 = rel_lum(rgb1), rel_lum(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, round(c)))) for c in rgb)


# ---- extraction ----
def _photo_colors(path, ncolors=8, thumb=96):
    """Median-cut palette of one image: list of (count, (r,g,b)). Deterministic."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((thumb, thumb), Image.LANCZOS)
    q = im.quantize(colors=ncolors, method=Image.MEDIANCUT)
    pal = q.getpalette()
    out = []
    for cnt, idx in (q.getcolors() or []):
        r, g, b = pal[idx * 3:idx * 3 + 3]
        out.append((cnt, (r, g, b)))
    return out

def _hue_items(color_counts):
    """(hue_deg, sat, val, weight) for colours that survive the grey/dark/blowout filter."""
    items = []
    for cnt, (r, g, b) in color_counts:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < SAT_DROP or v < VAL_LO or v > VAL_HI:
            continue
        items.append((h * 360, s, v, cnt * (0.5 + s)))   # weight = count x (0.5 + saturation)
    return items

def _bin_hues(items, binsize=HUE_BIN):
    """Merge neighbouring hues into weighted bins; representative hue = weighted circular mean."""
    bins = {}
    for h, s, v, w in items:
        b = int(h // binsize)
        acc = bins.setdefault(b, dict(w=0.0, sx=0.0, sy=0.0, sat=0.0))
        rad = math.radians(h)
        acc["w"] += w
        acc["sx"] += w * math.cos(rad)
        acc["sy"] += w * math.sin(rad)
        acc["sat"] += w * s
    out = []
    for b, acc in bins.items():
        if acc["w"] <= 0:
            continue
        hue = math.degrees(math.atan2(acc["sy"], acc["sx"])) % 360
        out.append(dict(hue=hue, sat=acc["sat"] / acc["w"], w=acc["w"]))
    # rank by weight; tie-break by hue so the order is fully deterministic
    out.sort(key=lambda d: (-d["w"], d["hue"]))
    return out

def _hue_dist(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)

def _pick_two(bins):
    if not bins:
        return None, None
    a = bins[0]
    for cand in bins[1:]:
        if _hue_dist(cand["hue"], a["hue"]) >= HUE_GAP:
            return a, cand
    return a, None


# ---- lightness clamp + pick-by-contrast ink ----
def _safe_color_and_ink(hue, sat):
    """Lowest lightness in the L 55-90 band whose colour clears MIN_CONTRAST against the
    better of the two inks. Values are rounded to the integers we actually store, so the
    stored hex is guaranteed to pass. Returns (rgb_int, ink_hex, ratio)."""
    sat = min(sat, SAT_CAP)
    ink_d, ink_l = hex_to_rgb(INK), hex_to_rgb(NIGHT_INK)
    for Lp in range(55, 91):                       # DESIGN band is L 55-80; extend to 90 for deep hues
        L = Lp / 100
        fr, fg, fb = colorsys.hls_to_rgb(hue / 360, L, sat)
        rgb = (round(fr * 255), round(fg * 255), round(fb * 255))
        cd, cn = contrast(rgb, ink_d), contrast(rgb, ink_l)
        ink, cc = (INK, cd) if cd >= cn else (NIGHT_INK, cn)
        if cc >= MIN_CONTRAST:
            return rgb, ink, cc
    # extreme hue: fall back to a near-white tint with dark ink (always passes)
    fr, fg, fb = colorsys.hls_to_rgb(hue / 360, 0.90, min(sat, 0.40))
    rgb = (round(fr * 255), round(fg * 255), round(fb * 255))
    return rgb, INK, contrast(rgb, hex_to_rgb(INK))

def _ink_for(accent_hex):
    """Pick-by-contrast ink for a fixed accent (fallback / override paths)."""
    a = hex_to_rgb(accent_hex)
    cd, cn = contrast(a, hex_to_rgb(INK)), contrast(a, hex_to_rgb(NIGHT_INK))
    return (INK, cd) if cd >= cn else (NIGHT_INK, cn)

def _finalize(accent_hex, support_hex, ink_hex=None):
    if ink_hex is None:
        ink_hex, cc = _ink_for(accent_hex)
    else:
        cc = contrast(hex_to_rgb(accent_hex), hex_to_rgb(ink_hex))
    assert cc >= MIN_CONTRAST, (
        f"guest_palette: accent {accent_hex} vs ink {ink_hex} is {cc:.2f}:1 (<{MIN_CONTRAST})")
    return dict(guest_accent=accent_hex.lower(), guest_support=support_hex.lower(), accent_ink=ink_hex.lower())

def _fallback():
    return _finalize(FALLBACK_ACCENT, FALLBACK_SUPPORT)


# ---- public API ----
def load_overrides():
    """Optional per-guest veto file: {cid: {"accent","support","ink"}}. Absent -> {}."""
    if OVERRIDE_FILE.exists():
        raw = json.loads(OVERRIDE_FILE.read_text())
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    return {}

def derive_tokens(photo_ids_ordered, cache_dir=CACHE):
    """photo_ids_ordered: the guest's focus photos, best-first. Reads up to N_PHOTOS of them."""
    items, n = [], 0
    for pid in photo_ids_ordered:
        p = Path(cache_dir) / pid
        if not p.exists():
            continue
        try:
            items.extend(_hue_items(_photo_colors(p)))
        except Exception:
            continue
        n += 1
        if n >= N_PHOTOS:
            break
    if not any(s > SAT_FLOOR for (_h, s, _v, _w) in items):
        return _fallback()
    bins = _bin_hues(items)
    a, b = _pick_two(bins)
    if a is None:
        return _fallback()
    acc_rgb, acc_ink, _ = _safe_color_and_ink(a["hue"], a["sat"])
    if b is not None:
        sup_rgb, _si, _sc = _safe_color_and_ink(b["hue"], b["sat"])
        support = rgb_to_hex(sup_rgb)
    else:
        support = FALLBACK_SUPPORT
    return _finalize(rgb_to_hex(acc_rgb), support, acc_ink)

def build_tokens(cid, pp, my_ids, cache_dir=CACHE, override=None):
    """Tokens for one guest. pp = photo_people dataframe; my_ids = the guest's cluster ids.
    override (dict) short-circuits extraction (human veto)."""
    if override:
        return _finalize(override["accent"], override.get("support", FALLBACK_SUPPORT), override.get("ink"))
    foc = pp[(pp.cluster_id.isin(my_ids)) & (pp.role == "focus")]
    # rank best-first, deterministic tie-break on photo_id
    foc = foc.sort_values(["score", "photo_id"], ascending=[False, True])
    seen, ids = set(), []
    for pid in foc.photo_id:
        if pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)
    return derive_tokens(ids, cache_dir)


if __name__ == "__main__":
    import argparse, pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", type=int, required=True)
    a = ap.parse_args()
    pp = pd.read_parquet(D / "photo_people.parquet")
    ov = load_overrides().get(str(a.cluster))
    print(build_tokens(a.cluster, pp, {a.cluster}, override=ov))
