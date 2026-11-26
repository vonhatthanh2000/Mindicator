from liqdash import db
from liqdash.parser import parse_message

TEXT = "🔴 #ETH Liquidated Long: $757K at $1642.96\nnot a liquidation"


def test_schema_creation_is_idempotent(tmp_path):
    path = tmp_path / "t.db"
    db.connect(path).close()
    conn = db.connect(path)
    tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {"liquidations", "skipped_lines", "sync_state", "symbols", "klines_1h", "oi_daily", "market_snapshots"} <= tables


def test_rerun_inserts_nothing_new(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    rows, skipped = parse_message(1, 100, TEXT)
    assert db.insert_liquidations(conn, rows) == 1
    assert db.insert_skipped(conn, skipped) == 1
    assert db.insert_liquidations(conn, rows) == 0
    assert db.insert_skipped(conn, skipped) == 0
    assert conn.execute("select count(*) from liquidations").fetchone()[0] == 1
    assert conn.execute("select count(*) from skipped_lines").fetchone()[0] == 1


def test_sync_state_roundtrip(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    assert db.get_sync_state(conn) is None
    db.set_sync_state(conn, last_msg_id=42, last_summary="x")
    db.set_sync_state(conn, last_msg_id=43)
    state = db.get_sync_state(conn)
    assert state["last_msg_id"] == 43 and state["last_summary"] == "x" and state["first_sync_utc"] is None
