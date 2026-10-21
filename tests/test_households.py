import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from household import hh_key, households, render_hub, _reroot


def _m(name, first, party="", token="tok", n=10, link=True, hero="../img/l/WEDDING/NP-1.jpg"):
    return dict(name=name, first=first, party=party, token=token, n_photos=n, link=link, hero=hero)


# --- household grouping -------------------------------------------------------------------

def test_party_groups_people_together():
    m = [_m("Neel N", "Neel", party="p1"), _m("Preethi R", "Preethi", party="p1")]
    assert list(households(m)) == ["p1"]
    assert len(households(m)["p1"]) == 2


def test_people_without_a_party_stay_separate():
    """No party must never collapse two strangers into one household."""
    m = [_m("Amelia T", "Amelia"), _m("James J", "James")]
    assert len(households(m)) == 2


def test_blank_and_whitespace_party_are_not_a_household():
    """A whitespace-only party column is absence, not a shared household."""
    assert hh_key("   ", "Amelia T") == "solo:Amelia T"
    assert hh_key("", "James J") == "solo:James J"
    assert hh_key(None, "Lily S") == "solo:Lily S"


def test_members_are_ordered_by_photo_count_desc():
    m = [_m("A A", "A", party="p", n=5), _m("B B", "B", party="p", n=50)]
    assert [x["first"] for x in households(m)["p"]] == ["B", "A"]


def test_make_emails_uses_the_same_key():
    """The email's household grouping and the hub's member list must not drift."""
    import make_emails
    assert make_emails.hh_key is hh_key


# --- image paths --------------------------------------------------------------------------

def test_reroot_adds_one_level_for_the_deeper_hub_page():
    # decks sit at /<token>/ and use ../img; hubs sit at /h/<token>/ and need ../../img
    assert _reroot("../img/l/WEDDING/NP-1.jpg") == "../../img/l/WEDDING/NP-1.jpg"


def test_reroot_leaves_absolute_urls_alone():
    assert _reroot("https://x.test/a.jpg") == "https://x.test/a.jpg"
    assert _reroot("/img/a.jpg") == "/img/a.jpg"
    assert _reroot("") == ""


# --- rendering ----------------------------------------------------------------------------

def test_hub_links_to_every_member_deck():
    html = render_hub("Neel & Preethi", [_m("Neel N", "Neel", token="aaa"), _m("Preethi R", "Preethi", token="bbb")])
    assert 'href="../../aaa/"' in html and 'href="../../bbb/"' in html
    assert "Neel" in html and "Preethi" in html


def test_glimpse_member_gets_a_photo_not_a_dead_deck_link():
    """link=False guests have no deck; the hub must not point at a folder that isn't built."""
    html = render_hub("Fam", [_m("Neel N", "Neel", token="aaa"), _m("Rita T", "Rita", token="ccc", link=False)])
    assert 'href="../../ccc/"' not in html
    assert "download" in html


def test_hub_never_contains_an_email_or_guest_id():
    """The PII contract: first names, photos, counts and links only.

    Matched as an address shape rather than a bare "@" — the stylesheet has @media rules.
    """
    m = _m("Neel N", "Neel", party="p1")
    m.update(email="someone@gmail.com", guest_id="g-123", personal_email=True)
    html = render_hub("Neel & Preethi", [m, _m("Preethi R", "Preethi", party="p1", token="bbb")])
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html)
    assert "guest_id" not in html and "g-123" not in html


def test_hub_escapes_names():
    html = render_hub('Ann & "Bob" <x>', [_m("A A", "A<script>", token="aaa")])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_hub_is_self_contained():
    """Same contract as the postcard: no bundle, no fetch, no external assets."""
    html = render_hub("Fam", [_m("A A", "A", token="aaa"), _m("B B", "B", token="bbb")])
    assert "<script" not in html
    assert not re.search(r'src="https?://', html)


# --- email link construction (regression) -------------------------------------------------

def test_abs_url_does_not_double_an_already_absolute_url():
    """build_guests.py writes absolute urls when run with --base-url (as docs/DEPLOY.md says).

    Prefixing base again produced "https://host.devhttps://host.dev/<token>/" in every
    generated email -- every guest link unopenable. Guard the join.
    """
    from make_emails import abs_url
    base = "https://wedding-wrapped.pages.dev"
    assert abs_url(base, f"{base}/abc123/") == f"{base}/abc123/"
    assert abs_url(base, "/abc123/") == f"{base}/abc123/"
    assert abs_url(base, "abc123/") == f"{base}/abc123/"
    assert abs_url(base, "") == ""
    assert abs_url(base, "http://x.test/a/") == "http://x.test/a/"


def test_no_generated_link_contains_two_schemes():
    from make_emails import abs_url
    base = "https://wedding-wrapped.pages.dev"
    for u in (f"{base}/t/", "/t/", "t/"):
        assert abs_url(base, u).count("://") == 1


# --- entry point: Hub asks whose Wrapped, root is the Login page ------------------------------

def test_hub_lede_asks_whose_wrapped():
    html = render_hub("Neel & Preethi", [_m("Neel N", "Neel", token="aaa"), _m("Preethi R", "Preethi", token="bbb")])
    assert "Select whose Wrapped you want to look at." in html


def test_root_is_the_login_page(tmp_path):
    from build_guests import write_root
    write_root(tmp_path)
    page = (tmp_path / "index.html").read_text()
    assert "/api/login" in page and 'type=email' in page
    assert "If we have that email, your link is on its way." in page
    assert 'href="sms:+15555550123"' in page and "+1-555-555-0123" in page
    assert (tmp_path / "_redirects").read_text().strip() == "/login / 301"
