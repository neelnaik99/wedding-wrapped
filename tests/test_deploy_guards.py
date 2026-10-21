"""deploy_site.sh run against a minimal fixture with a stub `npx` that records its arguments."""
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fixture(tmp_path, map_urls=("https://w.dev/abc/",), make_pages=("abc",)):
    shutil.copy(ROOT / "deploy_site.sh", tmp_path)
    site = tmp_path / "site_guest"; site.mkdir()
    (site / "index.html").write_text('<form action="/api/login"></form>')
    for p in make_pages:
        (site / p).mkdir(parents=True, exist_ok=True); (site / p / "index.html").write_text("ok")
    (site / "h" / "hh").mkdir(parents=True); (site / "h" / "hh" / "index.html").write_text("hub")
    lib = tmp_path / "functions" / "_lib"; lib.mkdir(parents=True)
    (lib / "login-map.json").write_text(json.dumps({f"g{i}@x.com": {"url": u, "greeting": "G"} for i, u in enumerate(map_urls)}))
    (tmp_path / "wrangler.toml").write_text('id = "real-id"\n')
    # The rule check re-runs from disk: photo_rule.py + data/ (photo_people, household_guard, tokens).
    import pandas as pd
    shutil.copy(ROOT / "photo_rule.py", tmp_path)
    (tmp_path / "data").mkdir()
    pd.DataFrame(dict(photo_id=["W/mine.jpg", "W/stranger.jpg"], cluster_id=[7, 99])).to_parquet(tmp_path / "data" / "photo_people.parquet")
    (tmp_path / "data" / "household_guard.json").write_text(json.dumps(dict(build_id="b1", couple=[15, 50], households={"hh": [7]}, person_tokens=["persontok1"])))
    (site / "h" / ".build_id").write_text("b1")
    (site / "h" / "hh" / "household.json").write_text(json.dumps(dict(shots=["../../img/l/W/mine.jpg"])))
    (bin_ := tmp_path / "bin").mkdir()
    (bin_ / "npx").write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\n'); (bin_ / "npx").chmod(0o755)
    return tmp_path


def _run(d, *args):
    env = dict(os.environ, WW_PYTHON=sys.executable, PATH=f"{d / 'bin'}:{os.environ['PATH']}")
    return subprocess.run(["zsh", str(d / "deploy_site.sh"), *args], cwd=d, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def test_preview_branch_reaches_wrangler_as_its_own_flag(tmp_path):
    r = _run(_fixture(tmp_path), "wedding-wrapped", "preview")
    assert r.returncode == 0, r.stdout + r.stderr
    args = [l[4:] for l in r.stdout.splitlines() if l.startswith("ARG:")]
    assert args[-2:] == ["--branch", "preview"] or "--branch=preview" in args


def test_dead_link_in_login_map_blocks_deploy(tmp_path):
    r = _run(_fixture(tmp_path, map_urls=("https://w.dev/h/gone/",), make_pages=()))
    assert r.returncode != 0 and "login map" in r.stdout


def test_relative_link_in_login_map_blocks_deploy(tmp_path):
    r = _run(_fixture(tmp_path, map_urls=("/abc/",)))
    assert r.returncode != 0 and "login map" in r.stdout


def test_email_in_household_json_blocks_deploy(tmp_path):
    d = _fixture(tmp_path)
    (d / "site_guest" / "h" / "hh" / "household.json").write_text('{"title": "a@gmail.com"}')
    r = _run(d)
    assert r.returncode != 0 and "PII in a Household Deck" in r.stdout


def test_bundle_copy_in_h_is_not_flagged_for_naming_guest_id(tmp_path):
    d = _fixture(tmp_path)
    (d / "app").mkdir(); (d / "app" / "bundle.html").write_text("<script>row.guest_id</script>")
    (d / "site_guest" / "h" / "hh" / "index.html").write_text("<script>row.guest_id</script>")
    r = _run(d)
    assert r.returncode == 0, r.stdout + r.stderr


def test_rule_violation_blocks_deploy(tmp_path):
    d = _fixture(tmp_path)
    (d / "site_guest" / "h" / "hh" / "household.json").write_text(json.dumps(dict(shots=["../../img/l/W/stranger.jpg"])))
    r = _run(d)
    assert r.returncode != 0 and "photo rule" in r.stdout and "W/stranger.jpg" in r.stdout
    assert "ARG:" not in r.stdout   # never reached wrangler


def test_missing_guard_data_blocks_deploy(tmp_path):
    d = _fixture(tmp_path)
    (d / "data" / "household_guard.json").unlink()
    r = _run(d)
    assert r.returncode != 0 and "photo rule" in r.stdout


def test_personal_deck_token_in_household_json_blocks_deploy(tmp_path):
    d = _fixture(tmp_path)
    (d / "site_guest" / "h" / "hh" / "household.json").write_text(json.dumps(dict(members=[dict(url="/persontok1/")])))
    r = _run(d)
    assert r.returncode != 0 and "persontok1" in r.stdout


def test_guard_from_another_build_blocks_deploy(tmp_path):
    d = _fixture(tmp_path)
    (d / "site_guest" / "h" / ".build_id").write_text("a-newer-build")
    r = _run(d)
    assert r.returncode != 0 and "different build" in r.stdout and "ARG:" not in r.stdout


def test_site_without_build_id_blocks_deploy(tmp_path):
    d = _fixture(tmp_path)
    (d / "site_guest" / "h" / ".build_id").unlink()
    r = _run(d)
    assert r.returncode != 0 and "different build" in r.stdout
