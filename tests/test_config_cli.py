import os
import subprocess
import sys

import pytest

from liqdash.config import ConfigError, Settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_require_names_missing_key():
    s = Settings(TG_API_ID=None)
    with pytest.raises(ConfigError, match="TG_API_ID"):
        s.require("TG_API_ID")


def test_require_returns_values():
    assert Settings(TG_API_ID="1", TG_API_HASH="h").require("TG_API_ID", "TG_API_HASH") == ["1", "h"]


def run_import(tmp_path, content, db_name="t.db"):
    src = tmp_path / "in.jsonl"
    src.write_text(content, encoding="utf-8")
    env = {**os.environ, "LIQ_DB": str(tmp_path / db_name)}
    code = "from liqdash.cli import import_main; import_main()"
    return subprocess.run([sys.executable, "-c", code, str(src)], cwd=ROOT, env=env, capture_output=True, text=True)


def test_malformed_lines_reported_and_skipped(tmp_path):
    good = '{"id": 1, "date_utc7": "2026-11-25T07:39:00+07:00", "text": "🔴 #ETH Liquidated Long: $1K at $1"}'
    content = "\n".join([good, "{not json", '{"id": 2}', '{"id": 3, "date_utc7": "bad", "text": ""}']) + "\n"
    r = run_import(tmp_path, content)
    assert r.returncode == 0, r.stderr
    assert "Synced 1 messages → 1 liquidations, 0 skipped lines." in r.stdout
    for n in (2, 3, 4):
        assert f"in.jsonl:{n}: skipped malformed line" in r.stderr


def test_refuses_live_db(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text("", encoding="utf-8")
    env = {**os.environ, "LIQ_DB": ""}
    code = "from liqdash.cli import import_main; import_main()"
    r = subprocess.run([sys.executable, "-c", code, str(src)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 1
    assert "Refusing to import into the live DB; set LIQ_DB" in r.stdout
    assert not (tmp_path / "liquidations.db").exists()
