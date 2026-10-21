"""household_deck: one Deck per Household (docs/adr/0002-one-deck-per-household.md)."""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from household_deck import (build_household_json, deck_title, everyone_index, subset_key,
                            write_household)

COUPLE = {15, 50}


def _shot(pid, time="10:00 AM"):
    return dict(id=pid, url=f"../img/l/{pid}", s=f"../img/s/{pid}", thumbs=[], n_alt=0,
                time=time, portrait=False, event="Wedding")


def _wrapped(cid, pids, map_pids=()):
    return dict(name=str(cid), cluster=cid, hero=f"../img/l/{pids[0]}", n_photos=len(pids),
                gallery=[dict(name="You in focus", n_all=len(pids), shots=[_shot(p) for p in pids])],
                picks=["../img/l/WEDDING/C-1.jpg"], costars=[],
                groups=[dict(id="g1", name="Crew", members=[],
                             map=dict(photos=[dict(id=p, s=f"../img/s/{p}", l=f"../img/l/{p}",
                                                   gallery="Wedding", mem=[cid]) for p in map_pids]))])


def _photos(pids):
    return pd.DataFrame(dict(photo_id=pids, gallery=["WEDDING"] * len(pids),
                             t=pd.to_datetime([f"2026-04-25 1{i % 10}:00:00" for i in range(len(pids))])))


def _member(cid, first, pids, **kw):
    return dict(cid=cid, first=first, light=False, wrapped=_wrapped(cid, pids, **kw))


# --- title (Decision 2) ---------------------------------------------------------------------

def test_title_prefers_envelope():
    assert deck_title("The Nolan Family", ["Gary", "Susan"]) == "The Nolan Family"
    assert deck_title("  ", ["Gary", "Susan"]) == "Gary & Susan"


def test_title_envelope_must_cover_a_multi_member_household():
    # one person's name on the envelope of a two-person Household: first names instead
    assert deck_title("Dana Moore", ["Parker", "Dana"]) == "Parker & Dana"
    assert deck_title("Paula Baker", ["Baker", "Paula"]) == "Baker & Paula"
    assert deck_title("Ursula Smith", ["Ryan", "Sofia"]) == "Ryan & Sofia"
    # plausible covers: "&", " and ", "family" (any case)
    assert deck_title("Parker & Dana Moore", ["Parker", "Dana"]) == "Parker & Dana Moore"
    assert deck_title("Mr. and Mrs. Smith", ["Ryan", "Sofia"]) == "Mr. and Mrs. Smith"
    assert deck_title("The Smith FAMILY", ["Ryan", "Sofia", "Ursula"]) == "The Smith FAMILY"
    # "and" inside a word is not a conjunction
    assert deck_title("Scott Andy", ["Scott", "Mia"]) == "Scott & Mia"


def test_title_any_envelope_for_one_member():
    assert deck_title("Dana Moore", ["Dana"]) == "Dana Moore"


def test_title_fallback_four_members():
    assert deck_title("", ["A", "B", "C", "D"]) == "A & B & C & family"
    assert deck_title("", ["A", "B", "C"]) == "A & B & C"


def test_subset_key_is_sorted_and_comma_joined():
    assert subset_key([50, 15]) == "15,50"


# --- household.json -------------------------------------------------------------------------

def test_who_tags_each_shot():
    by_photo = {"W/a.jpg": {1}, "W/b.jpg": {1, 2}, "W/c.jpg": {2, 99}}
    hh = build_household_json([_member(1, "A", ["W/a.jpg", "W/b.jpg"], map_pids=["W/b.jpg"]),
                               _member(2, "B", ["W/b.jpg", "W/c.jpg"])],
                              by_photo, COUPLE, photos=_photos(list(by_photo)))
    a, b = hh["members"]
    assert [s["who"] for s in a["wrapped"]["gallery"][0]["shots"]] == [[1], [1, 2]]
    assert [s["who"] for s in b["wrapped"]["gallery"][0]["shots"]] == [[1, 2], [2]]
    assert a["wrapped"]["groups"][0]["map"]["photos"][0]["who"] == [1, 2]


def test_household_json_shape():
    by_photo = {"W/a.jpg": {1}}
    hh = build_household_json([_member(1, "A", ["W/a.jpg"])], by_photo, COUPLE,
                              title="The A Family", photos=_photos(["W/a.jpg"]))
    assert set(hh) == {"title", "couple", "members", "summary", "face_src"}
    assert hh["title"] == "The A Family" and hh["couple"] == [15, 50]
    assert set(hh["members"][0]) == {"cid", "first", "light", "wrapped"}
    ev = hh["summary"]["1"]["events"][0]
    assert {"key", "name", "n", "first", "last", "day"} <= set(ev)


def test_member_wrapped_is_stripped_and_rerooted():
    """A shot showing only a stranger never ships; paths gain one ../ for the /h/<token>/ page."""
    by_photo = {"W/a.jpg": {1}, "W/x.jpg": {99}, "WEDDING/C-1.jpg": {15, 50}}
    hh = build_household_json([_member(1, "A", ["W/a.jpg", "W/x.jpg"])], by_photo, COUPLE,
                              photos=_photos(["W/a.jpg", "W/x.jpg"]))
    w = hh["members"][0]["wrapped"]
    assert [s["url"] for s in w["gallery"][0]["shots"]] == ["../../img/l/W/a.jpg"]
    assert w["hero"] == "../../img/l/W/a.jpg"
    assert w["picks"] == ["../../img/l/WEDDING/C-1.jpg"]


def test_merged_fragment_counts_as_the_member():
    """`ids` carries a member's merged clusters: a photo of fragment 7 is a photo of member 1."""
    by_photo = {"W/a.jpg": {7}}
    m = dict(_member(1, "A", ["W/a.jpg"]), ids={1, 7})
    hh = build_household_json([m], by_photo, COUPLE, photos=_photos(["W/a.jpg"]))
    assert hh["members"][0]["wrapped"]["gallery"][0]["shots"][0]["who"] == [1]
    assert "ids" not in hh["members"][0]


def test_summary_has_every_nonempty_subset():
    pids = ["W/a.jpg", "W/b.jpg", "W/c.jpg"]
    by_photo = {"W/a.jpg": {1}, "W/b.jpg": {2}, "W/c.jpg": {3}}
    hh = build_household_json([_member(1, "A", ["W/a.jpg"]), _member(2, "B", ["W/b.jpg"]),
                               _member(3, "C", ["W/c.jpg"])], by_photo, COUPLE, photos=_photos(pids))
    assert set(hh["summary"]) == {"1", "2", "3", "1,2", "1,3", "2,3", "1,2,3"}


def test_summary_counts_are_unions():
    pids = ["W/a.jpg", "W/b.jpg", "W/c.jpg"]
    by_photo = {"W/a.jpg": {1}, "W/b.jpg": {1, 2}, "W/c.jpg": {2}}
    hh = build_household_json([_member(1, "A", ["W/a.jpg", "W/b.jpg"]),
                               _member(2, "B", ["W/b.jpg", "W/c.jpg"])], by_photo, COUPLE,
                              photos=_photos(pids))
    s = hh["summary"]
    assert s["1"]["n_photos"] == 2 and s["2"]["n_photos"] == 2
    assert s["1,2"]["n_photos"] == 3          # the shared photo counts once
    assert s["1,2"]["n_events"] == 1 and s["1,2"]["events"][0]["n"] == 3


# --- files on disk --------------------------------------------------------------------------

def test_write_household_writes_page_json_and_pools(tmp_path):
    bundle = tmp_path / "bundle.html"; bundle.write_text("<html>bundle</html>")
    hh = dict(title="T", couple=[15, 50], members=[], summary={})
    pools = {1: {"photos": [dict(url="../../img/l/W/a.jpg", zone="shown", rank=0.5, who=[1])]}}
    write_household(tmp_path / "h" / "tok", hh, bundle, pools=pools)
    d = tmp_path / "h" / "tok"
    assert (d / "index.html").read_text() == "<html>bundle</html>"
    assert json.loads((d / "household.json").read_text()) == hh
    assert json.loads((d / "pool-1.json").read_text()) == pools[1]


def _guest_dir(site, tok, cid, pids):
    (site / tok).mkdir(parents=True)
    (site / tok / "wrapped.json").write_text(json.dumps(_wrapped(cid, pids)))
    (site / tok / "pool.json").write_text(json.dumps(
        {"photos": [dict(url=f"../img/l/{p}", zone="shown", rank=0.5) for p in pids]}))


def test_solo_household_gets_a_deck(tmp_path):
    from build_guests import build_household_decks
    site = tmp_path / "site"; bundle = tmp_path / "bundle.html"; bundle.write_text("bundle")
    _guest_dir(site, "aaa", 1, ["W/a.jpg", "W/x.jpg"])
    _guest_dir(site, "bbb", 2, ["W/b.jpg"]); _guest_dir(site, "ccc", 3, ["W/c.jpg"])
    manifest = [dict(name="Solo One", first="Solo", party="", token="aaa", n_photos=2, tier="group",
                     email="solo@example.com", guest_id="g-1", cluster=1),
                dict(name="Bo B", first="Bo", party="p1", token="bbb", n_photos=1, tier="group",
                     email="", guest_id="g-2", cluster=2),
                dict(name="Cy C", first="Cy", party="p1", token="ccc", n_photos=1, tier="cameo",
                     email="", guest_id="g-3", cluster=3)]
    tokens = {"hh:p1": "existingtk"}
    by_photo = {"W/a.jpg": {1}, "W/x.jpg": {99}, "W/b.jpg": {2}, "W/c.jpg": {3}}
    decks = build_household_decks(site, manifest, tokens, "https://w.dev", by_photo,
                                  ids_of={1: {1}, 2: {2}, 3: {3}}, couple=COUPLE,
                                  envelopes={"p1": "The B Family"}, photos=_photos(list(by_photo)),
                                  bundle_html=bundle)
    assert len(decks) == 2
    solo_tok = tokens["hh:solo:Solo One"]
    assert tokens["hh:p1"] == "existingtk"                      # never re-minted
    d = site / "h" / solo_tok
    assert (d / "index.html").exists()
    hh = json.loads((d / "household.json").read_text())
    assert [m["cid"] for m in hh["members"]] == [1] and hh["title"] == "Solo"
    assert manifest[0]["hub_url"] == f"https://w.dev/h/{solo_tok}/"
    assert manifest[1]["hub_url"] == manifest[2]["hub_url"] == "https://w.dev/h/existingtk/"
    fam = json.loads((site / "h" / "existingtk" / "household.json").read_text())
    assert fam["title"] == "The B Family" and set(fam["summary"]) == {"2", "3", "2,3"}
    # pool copied per member, stripped of the stranger-only photo
    pool = json.loads((d / "pool-1.json").read_text())["photos"]
    assert [p["url"] for p in pool] == ["../../img/l/W/a.jpg"] and pool[0]["who"] == [1]
    # PII contract: no email address or guest id anywhere under h/
    for f in (site / "h").rglob("*.json"):
        text = f.read_text()
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text) and "guest_id" not in text and "g-1" not in text


def test_everyone_index_lists_households(tmp_path):
    everyone_index(tmp_path / "h" / "all", [
        dict(title="The Nolan Family", hero="../../img/l/W/a.jpg", url="../aaa/"),
        dict(title="Solo & <Guest>", hero="", url="../bbb/")])
    page = (tmp_path / "h" / "all" / "index.html").read_text()
    assert "The Nolan Family" in page and 'href="../aaa/"' in page and 'href="../bbb/"' in page
    assert 'src="../../img/l/W/a.jpg"' in page
    assert "&lt;Guest&gt;" in page and "<script" not in page


# ---- Task 6: light tier ----
def test_light_member_in_family_is_selectable():
    ms = [dict(cid=2, first="Bo", light=True, wrapped=_wrapped(2, ["W/b.jpg"])),
          dict(cid=3, first="Cy", light=False, wrapped=_wrapped(3, ["W/c.jpg"]))]
    hh = build_household_json(ms, {"W/b.jpg": {2}, "W/c.jpg": {3}}, COUPLE, photos=_photos(["W/b.jpg", "W/c.jpg"]))
    assert [(m["cid"], m["light"]) for m in hh["members"]] == [(2, True), (3, False)]
    assert "mode" not in hh                                     # multi-member Household stays a normal Deck


def test_solo_light_household_is_light_mode():
    one = [dict(cid=2, first="Bo", light=True, wrapped=_wrapped(2, ["W/b.jpg"]))]
    hh = build_household_json(one, {"W/b.jpg": {2}}, COUPLE, photos=_photos(["W/b.jpg"]))
    assert hh["mode"] == "light"
    solo = [dict(cid=2, first="Bo", light=False, wrapped=_wrapped(2, ["W/b.jpg"]))]
    assert "mode" not in build_household_json(solo, {"W/b.jpg": {2}}, COUPLE, photos=_photos(["W/b.jpg"]))


def test_build_household_decks_carries_light_from_manifest_tier(tmp_path):
    from build_guests import build_household_decks
    site = tmp_path / "site"; bundle = tmp_path / "bundle.html"; bundle.write_text("b")
    _guest_dir(site, "aaa", 1, ["W/a.jpg"]); _guest_dir(site, "bbb", 2, ["W/b.jpg"])
    manifest = [dict(name="Lo L", first="Lo", party="", token="aaa", n_photos=1, tier="light", email="", guest_id="g-1", cluster=1),
                dict(name="No N", first="No", party="", token="bbb", n_photos=1, tier="cameo", email="", guest_id="g-2", cluster=2)]
    tokens = {}
    decks = build_household_decks(site, manifest, tokens, "", {"W/a.jpg": {1}, "W/b.jpg": {2}}, {1: {1}, 2: {2}}, COUPLE, {},
                                  photos=_photos(["W/a.jpg", "W/b.jpg"]), bundle_html=bundle)
    modes = {d["members"][0]: json.loads((site / "h" / d["token"] / "household.json").read_text()).get("mode") for d in decks}
    assert modes == {"aaa": "light", "bbb": None}


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "data" / "faces.parquet").exists(),
                    reason="label_server loads private face data at import")
def test_override_tier_accepts_light():
    import importlib, build_wrapped
    argv = sys.argv; sys.argv = ["label_server"]       # label_server parses argv at import
    try: label_server = importlib.import_module("label_server")
    finally: sys.argv = argv
    assert "light" in label_server.VALID_TIERS
    assert build_wrapped.tier_of(7, 500, {"7": "light"}) == "light"


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "data" / "faces.parquet").exists(),
                    reason="label_server loads private face data at import")
def test_review_payload_all_guests_includes_unflagged(monkeypatch):
    import importlib
    argv = sys.argv; sys.argv = ["label_server"]
    try: ls = importlib.import_module("label_server")
    finally: sys.argv = argv
    rows = [dict(cid=1, name="Flagged", flags=["boundary"], boundary_distance=2, tier="cameo"),
            dict(cid=2, name="Clear", flags=[], boundary_distance=90, tier="inner")]
    monkeypatch.setattr(ls, "_review_ctx", lambda: ({}, None, {}, {}, {}))
    monkeypatch.setattr(ls, "_review_guest_cids", lambda: [1, 2])
    monkeypatch.setattr(ls, "_review_row", lambda cid, *a: next(r for r in rows if r["cid"] == cid))
    monkeypatch.setattr(ls, "_mtime", lambda p: 1)
    monkeypatch.setattr(ls, "load_review_state", lambda: {})
    monkeypatch.setitem(ls._rev, "sig", None)
    assert [r["cid"] for r in ls.review_queue_payload()["rows"]] == [1]                 # default unchanged
    full = ls.review_queue_payload(include_all=True)
    assert [r["cid"] for r in full["rows"]] == [1, 2] and full["total"] == 2
    assert full["rows"][1]["flags"] == [] and "light" in full["tiers"]


def test_group_members_carry_no_personal_deck_link():
    """Ruling (Task 2): household.json is publicly fetchable, so a group member's url/slug
    (another guest's personal deck link) must never be built into it."""
    w = _wrapped(20, ["WEDDING/a.jpg"]); w["slug"] = "ownslug123"
    w["groups"][0]["members"] = [dict(cid=7, name="Pat Q", first="Pat", face="../img/face_7.jpg",
                                      together=3, url="/udd96d3jgv/", slug="udd96d3jgv")]
    hh = build_household_json([dict(cid=20, first="Sam", light=False, wrapped=w)], {}, COUPLE,
                              photos=_photos(["WEDDING/a.jpg"]))
    (m,) = hh["members"][0]["wrapped"]["groups"][0]["members"]
    assert "url" not in m and "slug" not in m and "udd96d3jgv" not in json.dumps(hh) and "ownslug123" not in json.dumps(hh)
    assert m["first"] == "Pat" and m["together"] == 3


# ---- final review finding 3: per-Household face crops ----
def _faces_member():
    w = _wrapped(20, ["WEDDING/a.jpg"])
    w["costars"] = [dict(cid=7, n=5, name="Pat", img="../img/face_7.jpg", labeled=True),
                    dict(cid=21, n=4, name="Kim", img="../img/face_21.jpg", labeled=True),
                    dict(cid=15, n=3, name="Neel", img="../img/face_15.jpg", labeled=True, couple=True)]
    w["groups"][0]["members"] = [dict(cid=7, name="Pat Q", first="Pat", face="../img/face_7.jpg", together=3),
                                 dict(cid=8, name="Lee R", first="Lee", face="../img/face_8.jpg", together=1)]
    w["groups"][0]["map"]["members"] = [dict(cid=20, name="Sam", first="Sam", face="../img/face_20.jpg", r=30),
                                        dict(cid=7, name="Pat Q", first="Pat", face="../img/face_7.jpg", r=20),
                                        dict(cid=8, name="Lee R", first="Lee", face="../img/face_8.jpg", r=10)]
    return [dict(cid=20, first="Sam", light=False, wrapped=w),
            dict(cid=21, first="Kim", light=False, wrapped=_wrapped(21, ["WEDDING/b.jpg"]))]


def test_non_household_faces_become_per_household_crops_or_null():
    asked = []
    def pick(cid, hh_ids):
        asked.append((cid, frozenset(hh_ids)))
        return "WEDDING/a.jpg" if cid == 7 else None
    hh = build_household_json(_faces_member(), {"WEDDING/a.jpg": {20, 7}, "WEDDING/b.jpg": {21}}, COUPLE,
                              photos=_photos(["WEDDING/a.jpg", "WEDDING/b.jpg"]), face_pick=pick)
    w = hh["members"][0]["wrapped"]
    assert [c["img"] for c in w["costars"]] == ["faces/7.jpg", "../../img/face_21.jpg", "../../img/face_15.jpg"]
    assert [m["face"] for m in w["groups"][0]["members"]] == ["faces/7.jpg", None]
    assert [m["face"] for m in w["groups"][0]["map"]["members"]] == ["../../img/face_20.jpg", "faces/7.jpg", None]
    assert hh["face_src"] == {"7": "WEDDING/a.jpg"}
    assert sorted(c for c, _ in asked) == [7, 8] and asked[0][1] == {20, 21}    # once per person


def test_without_a_face_picker_non_household_faces_fail_closed_to_null():
    hh = build_household_json(_faces_member(), {"WEDDING/a.jpg": {20, 7}}, COUPLE,
                              photos=_photos(["WEDDING/a.jpg", "WEDDING/b.jpg"]))
    w = hh["members"][0]["wrapped"]
    assert [c["img"] for c in w["costars"]] == [None, "../../img/face_21.jpg", "../../img/face_15.jpg"]
    assert hh["face_src"] == {}


def test_write_household_writes_face_crops_and_drops_stale(tmp_path):
    d = tmp_path / "h" / "tok"; (d / "faces").mkdir(parents=True)
    (d / "faces" / "99.jpg").write_bytes(b"old")
    bundle = tmp_path / "b.html"; bundle.write_text("b")
    write_household(d, {"face_src": {"7": "W/a.jpg"}}, bundle,
                    faces={7: lambda out: Path(out).write_bytes(b"crop")})
    assert sorted(p.name for p in (d / "faces").iterdir()) == ["7.jpg"]
    assert (d / "faces" / "7.jpg").read_bytes() == b"crop"


def test_household_faces_picks_the_best_face_in_a_photo_with_a_member(tmp_path, monkeypatch):
    from build_guests import HouseholdFaces, build_household_decks
    import build_wrapped
    faces = pd.DataFrame(dict(
        photo_id=["W/big-stranger.jpg", "W/small-member.jpg", "W/large-member.jpg", "W/b.jpg", "W/a.jpg"],
        cluster_id=[7, 7, 70, 2, 1], x1=[0] * 5, y1=[0] * 5, x2=[9] * 5, y2=[9] * 5,
        size=[400, 50, 120, 80, 80], det_score=[0.99, 0.9, 0.8, 0.9, 0.9]))
    by_photo = {"W/big-stranger.jpg": {7, 99}, "W/small-member.jpg": {7, 1}, "W/large-member.jpg": {70, 1},
                "W/a.jpg": {1}, "W/b.jpg": {2}}
    hf = HouseholdFaces(faces, by_photo, lambda c: {7, 70} if c == 7 else {c})
    assert hf.pick(7, {1}) == "W/large-member.jpg"      # fragment 70 counts; the stranger-only photo never does
    assert hf.pick(7, {2}) is None
    # end to end: the Deck gets faces/7.jpg (written via crop_face) for member 1, nothing for member 2
    crops = []
    monkeypatch.setattr(build_wrapped, "crop_face", lambda f, out: (crops.append(f.photo_id), Path(out).write_bytes(b"j")))
    site = tmp_path / "site"; bundle = tmp_path / "b.html"; bundle.write_text("b")
    for tok, cid, pid in (("aaa", 1, "W/a.jpg"), ("bbb", 2, "W/b.jpg")):
        _guest_dir(site, tok, cid, [pid])
        w = json.loads((site / tok / "wrapped.json").read_text())
        w["costars"] = [dict(cid=7, n=2, name="Pat", img="../img/face_7.jpg", labeled=True)]
        (site / tok / "wrapped.json").write_text(json.dumps(w))
    manifest = [dict(name="A A", first="A", party="", token="aaa", n_photos=1, tier="group", cluster=1),
                dict(name="B B", first="B", party="", token="bbb", n_photos=1, tier="group", cluster=2)]
    decks = build_household_decks(site, manifest, {}, "", by_photo, {1: {1}, 2: {2}}, COUPLE, {},
                                  photos=_photos(list(by_photo)), bundle_html=bundle, faces=hf)
    got = {}
    for d in decks:
        hh = json.loads((site / "h" / d["token"] / "household.json").read_text())
        got[hh["members"][0]["cid"]] = (hh["members"][0]["wrapped"]["costars"][0]["img"],
                                         (site / "h" / d["token"] / "faces" / "7.jpg").exists())
    assert got == {1: ("faces/7.jpg", True), 2: (None, False)}
    assert crops == ["W/large-member.jpg"]
