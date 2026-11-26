import sqlite3

from liqdash.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS liquidations(
    msg_id INT, line_no INT, ts_utc INT, token TEXT,
    side TEXT CHECK(side IN ('Long','Short')), size_usd INT, price TEXT,
    PRIMARY KEY(msg_id, line_no));
CREATE INDEX IF NOT EXISTS ix_liq_token_ts ON liquidations(token, ts_utc);
CREATE INDEX IF NOT EXISTS ix_liq_ts ON liquidations(ts_utc);
CREATE TABLE IF NOT EXISTS skipped_lines(
    msg_id INT, line_no INT, ts_utc INT, raw TEXT,
    PRIMARY KEY(msg_id, line_no));
CREATE TABLE IF NOT EXISTS sync_state(
    id INT PRIMARY KEY CHECK(id=1), last_msg_id INT, first_sync_utc INT,
    last_sync_utc INT, last_summary TEXT);
CREATE TABLE IF NOT EXISTS symbols(
    token TEXT PRIMARY KEY, symbol TEXT NULL, contract_type TEXT NULL,
    is_crypto INT, updated_utc INT);
CREATE TABLE IF NOT EXISTS klines_1h(
    symbol TEXT, open_time_utc INT, open TEXT, close TEXT, quote_volume REAL,
    PRIMARY KEY(symbol, open_time_utc));
CREATE TABLE IF NOT EXISTS oi_daily(
    symbol TEXT, day TEXT, oi_usd REAL NULL,
    PRIMARY KEY(symbol, day));
CREATE TABLE IF NOT EXISTS market_snapshots(
    sync_utc INT, symbol TEXT, funding_rate REAL, mark_price TEXT,
    PRIMARY KEY(sync_utc, symbol));
"""


def connect(path=None):
    conn = sqlite3.connect(path or settings.LIQ_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def insert_liquidations(conn, rows):
    """Insert rows, return how many were new."""
    before = conn.total_changes
    conn.executemany("INSERT OR IGNORE INTO liquidations VALUES (?,?,?,?,?,?,?)", rows)
    return conn.total_changes - before


def insert_skipped(conn, rows):
    before = conn.total_changes
    conn.executemany("INSERT OR IGNORE INTO skipped_lines VALUES (?,?,?,?)", rows)
    return conn.total_changes - before


def get_sync_state(conn):
    row = conn.execute(
        "SELECT last_msg_id, first_sync_utc, last_sync_utc, last_summary FROM sync_state WHERE id=1"
    ).fetchone()
    if row is None:
        return None
    return dict(zip(("last_msg_id", "first_sync_utc", "last_sync_utc", "last_summary"), row))


def set_sync_state(conn, **fields):
    conn.execute("INSERT OR IGNORE INTO sync_state(id) VALUES (1)")
    for k, v in fields.items():
        conn.execute(f"UPDATE sync_state SET {k}=? WHERE id=1", (v,))
