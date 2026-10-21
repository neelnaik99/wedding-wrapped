"""make_emails.household_rows: the operator's files carry only the Household Link."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from make_emails import household_rows

BASE = "https://wedding-wrapped.pages.dev"


def _m(name, first, token, hub, n, email="", party="p1", link=True):
    return dict(name=name, first=first, token=token, url=f"{BASE}/{token}/", email=email, party=party,
                n_photos=n, link=link, hero="../img/l/HALDI/NP-1.jpg", hub_url=f"{BASE}/h/{hub}/")


def _g(first, last, party, email="", phone=""):
    return {"first name": first, "last name": last, "party": party, "email": email,
            "phone number": phone, "envelope name": ""}


MANIFEST = [
    _m("Ann Lee", "Ann", "persontokA1", "hhtokenAB", 90, party="p1"),
    _m("Bob Lee", "Bob", "persontokB2", "hhtokenAB", 40, party="p1"),
    _m("Cy Roe", "Cy", "persontokC3", "hhtokenCC", 30, party="p2"),
    _m("Di Roe", "Di", "persontokD4", "hhtokenCC", 5, party="p2", link=False),
]
GUESTS = [_g("Ann", "Lee", "p1", email="ann@example.com"), _g("Bob", "Lee", "p1"),
          _g("Cy", "Roe", "p2", phone="555-0100"), _g("Di", "Roe", "p2")]


def _rows():
    emails, no_email = household_rows(MANIFEST, GUESTS, BASE, "subj")
    return emails, no_email


def test_no_row_carries_a_per_person_deck_url():
    emails, no_email = _rows()
    assert len(emails) == 1 and len(no_email) == 1
    for row in emails + no_email:
        for col, val in row.items():
            for m in MANIFEST:
                assert m["token"] not in str(val), f"{col} carries {m['first']}'s personal deck"
        assert "links" not in row and "urls" not in row


def test_no_email_worklist_carries_the_household_link():
    _, no_email = _rows()
    (row,) = no_email
    assert row["login_url"] == f"{BASE}/h/hhtokenCC/"
    assert row["phones"] == "555-0100"


def test_copy_speaks_of_one_shared_household_page():
    emails, _ = _rows()
    (row,) = emails
    for body in (row["html_body"], row["text_body"]):
        assert not re.search(r"personal (photo )?recap|each of you", body)
    assert "put together the photos of your family from the weekend" in row["html_body"]
    assert "put together the photos of your family from the weekend" in row["text_body"]
