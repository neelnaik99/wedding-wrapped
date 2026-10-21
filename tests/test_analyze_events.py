import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analyze_events import zone_rates

POOLS = {
    "tokA": {"WEDDING/NP-1.jpg": "shown", "WEDDING/NP-2.jpg": "skipped", "WEDDING/NP-3.jpg": "below_bar"},
    "tokB": {"HALDI/NP-9.jpg": "shown"},
}

def _ev(slug, photo, action="select_on", env="prod"):
    return {"slug": slug, "photo": photo, "action": action, "surface": "all_photos", "env": env, "ts": "2026-09-01T00:00:00Z"}

def test_counts_selections_per_zone_over_active_guests():
    events = [
        _ev("tokA", "WEDDING/NP-1.jpg"),               # shown, selected
        _ev("tokA", "WEDDING/NP-2.jpg"),               # skipped, selected -> ranker miss
        _ev("tokA", "WEDDING/NP-2.jpg", "select_off"), # net off -> not selected
        _ev("tokA", "WEDDING/NP-3.jpg"),               # below_bar, selected -> threshold miss
    ]
    rates = zone_rates(events, POOLS)
    # only tokA is active (tokB logged nothing) -> denominators from tokA's pool only
    assert rates["shown"] == (1, 1)
    assert rates["skipped"] == (0, 1)   # net selection after the toggle-off is zero
    assert rates["below_bar"] == (1, 1)

def test_stage_events_are_excluded():
    events = [_ev("tokA", "WEDDING/NP-1.jpg", env="stage")]
    assert zone_rates(events, POOLS) == {}
