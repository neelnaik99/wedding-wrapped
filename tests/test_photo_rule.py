import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from photo_rule import allowed, strip_wrapped, violations

COUPLE = {15, 50}
HH = {7, 8}


def test_member_photo_allowed():
    assert allowed({7, 99}, HH, COUPLE)


def test_couple_only_photo_allowed():
    assert allowed({15, 50}, HH, COUPLE)
    assert allowed({50}, HH, COUPLE)


def test_couple_plus_stranger_rejected():
    assert not allowed({15, 50, 99}, HH, COUPLE)


def test_stranger_only_rejected():
    assert not allowed({99}, HH, COUPLE)


def test_empty_faces_rejected():
    assert not allowed(set(), HH, COUPLE)


def _url(pid, kind="l"):
    return f"../img/{kind}/{pid}"


def _shot(pid):
    return {"url": _url(pid), "thumbs": [_url(pid, "s")], "n_alt": 0,
            "time": "10:00", "portrait": False}


BY_PHOTO = {
    "HALDI/NP-169.jpg": {99},               # stranger -> hero, removed
    "RECEPTION COUPLE/NP-2.jpg": {15, 50},  # couple only -> kept
    "SANGEET_NIGHT/NP-5.jpg": {7, 99},      # member -> kept
    "HALDI/NP-300.jpg": {99, 98},           # stranger -> removed
    "MEHENDI/NP-9.jpg": {15, 50, 99},       # couple + stranger -> removed
}


def _wrapped():
    return {
        "hero": _url("HALDI/NP-169.jpg"),
        "gallery": [
            {"name": "Haldi", "n_all": 2,
             "shots": [_shot("HALDI/NP-169.jpg"), _shot("RECEPTION COUPLE/NP-2.jpg")]},
            {"name": "Sangeet", "n_all": 1, "shots": [_shot("SANGEET_NIGHT/NP-5.jpg")]},
        ],
        "picks": [_url("SANGEET_NIGHT/NP-5.jpg"), _url("HALDI/NP-300.jpg")],
        "groups": [{"id": 1, "name": "g", "members": [7], "map": {
            "photos": [
                {"id": "MEHENDI/NP-9.jpg", "s": _url("MEHENDI/NP-9.jpg", "s"),
                 "l": _url("MEHENDI/NP-9.jpg"), "mem": [15, 50, 99]},
                {"id": "SANGEET_NIGHT/NP-5.jpg", "s": _url("SANGEET_NIGHT/NP-5.jpg", "s"),
                 "l": _url("SANGEET_NIGHT/NP-5.jpg"), "mem": [7]},
            ]}}, {"id": 2, "name": "nomap", "members": [7], "map": None}],
    }


def test_strip_removes_and_counts():
    w = _wrapped()
    orig = json.dumps(w)
    out, n = strip_wrapped(w, BY_PHOTO, HH, COUPLE)
    assert json.dumps(w) == orig  # input untouched
    assert n == 3  # haldi shot + pick + map photo
    urls = [s["url"] for g in out["gallery"] for s in g["shots"]]
    assert urls == [_url("RECEPTION COUPLE/NP-2.jpg"), _url("SANGEET_NIGHT/NP-5.jpg")]
    assert out["hero"] == _url("RECEPTION COUPLE/NP-2.jpg")
    assert out["picks"] == [_url("SANGEET_NIGHT/NP-5.jpg")]
    assert [p["id"] for p in out["groups"][0]["map"]["photos"]] == ["SANGEET_NIGHT/NP-5.jpg"]
    assert out["groups"][1]["map"] is None


def test_violations_finds_a_planted_stray(tmp_path):
    good, bad = tmp_path / "h" / "goodtok", tmp_path / "h" / "badtok"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    ok, _ = strip_wrapped(_wrapped(), BY_PHOTO, HH, COUPLE)
    (good / "household.json").write_text(json.dumps(ok))
    (bad / "household.json").write_text(json.dumps(_wrapped()))
    got = violations(tmp_path, BY_PHOTO, {"goodtok": HH, "badtok": HH}, COUPLE)
    assert "badtok: HALDI/NP-169.jpg" in got
    assert "badtok: MEHENDI/NP-9.jpg" in got
    assert not any(v.startswith("goodtok") for v in got)


def test_unparseable_references_are_stripped_and_counted():
    w = _wrapped()
    w["gallery"][0]["shots"].append(_shot("HALDI/NP-1.jpg"))
    w["gallery"][0]["shots"][-1]["url"] = "../img/l/HALDI/NP-1.jpeg"
    w["picks"].append({"url": "../img/l/SANGEET_NIGHT/NP-5.jpg"})  # dict pick
    w["groups"][0]["map"]["photos"].append({"id": "x", "l": "../img/l/odd.png"})
    out, n = strip_wrapped(w, BY_PHOTO, HH, COUPLE)
    assert n == 6
    assert out["picks"] == [_url("SANGEET_NIGHT/NP-5.jpg")]
    assert all(".jpeg" not in s["url"] for g in out["gallery"] for s in g["shots"])


def test_thumbs_filtered_and_missing_shots_tolerated():
    w = _wrapped()
    w["gallery"][1]["shots"][0]["thumbs"] = [
        _url("SANGEET_NIGHT/NP-5.jpg", "s"), _url("HALDI/NP-300.jpg", "s")]
    w["gallery"].append({"name": "Empty", "n_all": 0})
    out, n = strip_wrapped(w, BY_PHOTO, HH, COUPLE)
    assert out["gallery"][1]["shots"][0]["thumbs"] == [_url("SANGEET_NIGHT/NP-5.jpg", "s")]
    assert out["gallery"][2]["shots"] == []
    assert n == 3


def test_hero_none_when_no_allowed_shot_survives():
    w = {"hero": _url("HALDI/NP-169.jpg"),
         "gallery": [{"name": "H", "shots": [_shot("HALDI/NP-169.jpg")]}],
         "picks": [], "groups": None}
    out, n = strip_wrapped(w, BY_PHOTO, HH, COUPLE)
    assert out["hero"] is None and n == 1
    assert out["groups"] is None


def test_hero_none_input_stays_none():
    out, n = strip_wrapped({"hero": None, "gallery": [], "picks": []}, BY_PHOTO, HH, COUPLE)
    assert out["hero"] is None and n == 0


def test_violations_pool_file_unknown_and_missing(tmp_path):
    (tmp_path / "h" / "tok").mkdir(parents=True)
    (tmp_path / "h" / "stranger").mkdir()
    pool = {"photos": [
        {"url": "../img/l/SANGEET_NIGHT/NP-5.jpg", "zone": "shown", "rank": 0.8},
        {"url": "../img/l/HALDI/NP-300.jpg", "zone": "shown", "rank": 0.1}]}
    (tmp_path / "h" / "tok" / "pool-7.json").write_text(json.dumps(pool, ensure_ascii=True))
    got = violations(tmp_path, BY_PHOTO, {"tok": HH, "gone": HH}, COUPLE)
    assert "tok: HALDI/NP-300.jpg" in got
    assert "tok: SANGEET_NIGHT/NP-5.jpg" not in got
    assert "stranger: unknown household" in got
    assert "gone: missing" in got


def test_leaked_tokens_finds_person_deck_token_in_household_json(tmp_path):
    from photo_rule import leaked_tokens
    d = tmp_path / "h" / "hhtoken001"; d.mkdir(parents=True)
    (d / "household.json").write_text('{"groups": [{"members": [{"url": "/abcdefghij/"}]}]}')
    assert leaked_tokens(tmp_path, {"abcdefghij"}) == ["hhtoken001: abcdefghij"]
    assert leaked_tokens(tmp_path, {"zzzzzzzzzz"}) == []


def test_leaked_tokens_scans_every_json_and_html_under_h(tmp_path):
    from photo_rule import leaked_tokens
    d = tmp_path / "h" / "hhtoken001"; d.mkdir(parents=True)
    (d / "household.json").write_text("{}")
    (d / "pool-7.json").write_text('{"photos": [{"url": "/abcdefghij/x.jpg"}]}')
    (d / "index.html").write_text('<a href="/klmnopqrst/">x</a>')
    assert leaked_tokens(tmp_path, {"abcdefghij", "klmnopqrst", "zzzzzzzzzz"}) == [
        "hhtoken001: abcdefghij", "hhtoken001: klmnopqrst"]


# --- face crops on a Household Deck (final review finding 3) ---------------------------------

def _face_site(tmp_path, refs, face_src=None, files=()):
    d = tmp_path / "h" / "tok"; (d / "faces").mkdir(parents=True)
    for cid in files:
        (d / "faces" / f"{cid}.jpg").write_bytes(b"jpg")
    hh = {"members": [{"wrapped": {"costars": [{"cid": c, "img": r} for c, r in refs]}}]}
    if face_src is not None:
        hh["face_src"] = face_src
    (d / "household.json").write_text(json.dumps(hh))
    return violations(tmp_path, BY_PHOTO, {"tok": HH}, COUPLE)


def test_site_wide_face_of_a_non_member_is_a_violation(tmp_path):
    got = _face_site(tmp_path, [(99, "../../img/face_99.jpg"), (7, "../../img/face_7.jpg"),
                                (15, "../../img/face_15.jpg")])
    assert got == ["tok: face ../../img/face_99.jpg is not this Household's crop"]


def test_per_household_crop_needs_a_member_photo_source_and_a_file(tmp_path):
    ok = _face_site(tmp_path, [(99, "faces/99.jpg")], face_src={"99": "SANGEET_NIGHT/NP-5.jpg"}, files=[99])
    assert ok == []


def test_per_household_crop_from_a_photo_without_a_member_fails(tmp_path):
    got = _face_site(tmp_path, [(99, "faces/99.jpg")], face_src={"99": "HALDI/NP-300.jpg"}, files=[99])
    assert any("faces/99.jpg" in v for v in got)


def test_per_household_crop_without_source_or_file_fails(tmp_path):
    assert any("faces/99.jpg" in v for v in _face_site(tmp_path, [(99, "faces/99.jpg")], face_src={}, files=[99]))


def test_crop_file_missing_fails(tmp_path):
    got = _face_site(tmp_path, [(99, "faces/99.jpg")], face_src={"99": "SANGEET_NIGHT/NP-5.jpg"})
    assert any("faces/99.jpg" in v for v in got)


def test_another_households_crop_or_unknown_face_path_fails(tmp_path):
    got = _face_site(tmp_path, [(99, "../other/faces/99.jpg"), (98, "../../img/faces/98.jpg")],
                     face_src={"99": "SANGEET_NIGHT/NP-5.jpg"}, files=[99])
    assert len(got) == 2


def test_null_face_is_fine(tmp_path):
    assert _face_site(tmp_path, [(99, None)]) == []
