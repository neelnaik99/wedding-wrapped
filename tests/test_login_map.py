import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from login_map import build_login_map


def _row(to, login_url="https://w.dev/h/tok/", greeting="Sydney & Jordan"):
    return dict(to=to, login_url=login_url, greeting=greeting)


def test_every_household_email_maps_to_its_link():
    m = build_login_map([_row("a@x.com; b@x.com", login_url="https://w.dev/h/tok/")])
    assert m["a@x.com"]["url"] == "https://w.dev/h/tok/"
    assert m["b@x.com"]["url"] == "https://w.dev/h/tok/"


def test_emails_are_normalised():
    """Guests type addresses however they like; the key must match the Login lookup's form."""
    m = build_login_map([_row(" Sydney@Gmail.COM ")])
    assert list(m) == ["sydney@gmail.com"]


def test_household_without_a_deck_is_absent():
    """No Deck means no Link to send — Login must treat the address as unknown."""
    assert build_login_map([_row("glimpse@x.com", login_url="")]) == {}


def test_greeting_carried():
    m = build_login_map([_row("a@x.com", greeting="Avery & Simon")])
    assert m["a@x.com"]["greeting"] == "Avery & Simon"


def test_duplicate_email_across_rows_raises():
    """One address in two Households would make Login pick one silently — refuse to build."""
    with pytest.raises(ValueError):
        build_login_map([_row("a@x.com", login_url="https://w.dev/1/"),
                         _row("A@x.com", login_url="https://w.dev/2/")])


# --- which Link a Household's Login email carries -----------------------------------------

from login_map import login_target


def _d(tok):
    return dict(url=f"https://w.dev/{tok}/", hub_url="")


def test_two_deck_members_get_the_hub():
    assert login_target("https://w.dev", "https://w.dev/h/hh/", [_d("a"), _d("b")]) == "https://w.dev/h/hh/"


def test_one_member_household_gets_its_household_link():
    """A one-person Household has a Household Deck too — its Link is that URL, not a per-person one."""
    assert login_target("https://w.dev", "https://w.dev/h/solo/", [_d("a")]) == "https://w.dev/h/solo/"


def test_every_email_in_a_household_gets_the_same_link():
    url = login_target("https://w.dev", "/h/hh/", [_d("a"), _d("b")])
    m = build_login_map([_row("a@x; b@x", login_url=url)])
    assert m["a@x"]["url"] == m["b@x"]["url"] == "https://w.dev/h/hh/"


def test_no_deck_gets_nothing():
    assert login_target("https://w.dev", "", []) == ""


def test_relative_links_are_made_absolute():
    """A manifest built without --base-url holds '/tok/'; an email needs a full URL."""
    assert login_target("https://w.dev", "/h/a/", [dict(url="/a/")]) == "https://w.dev/h/a/"


def test_extra_addresses_join_the_map():
    """The test address gets the everyone Hub alongside the guests' own entries."""
    m = build_login_map([_row("a@x.com")], extra={" Test@X.com": {"url": "https://w.dev/h/all/", "greeting": "Everyone"}})
    assert m["test@x.com"]["url"] == "https://w.dev/h/all/"
    assert "a@x.com" in m


def test_extra_address_that_is_also_a_guest_raises():
    with pytest.raises(ValueError):
        build_login_map([_row("a@x.com")], extra={"a@x.com": {"url": "https://w.dev/h/all/", "greeting": "Everyone"}})
