import json
import os
import sys
import time
from datetime import datetime

from liqdash import db
from liqdash.config import DEFAULT_DB, settings
from liqdash.parser import parse_message
from liqdash.telegram_sync import summary_text


def import_main():
    """liq-import <jsonl>: load {id, date_utc7, text} lines into LIQ_DB (never the live DB)."""
    if os.path.abspath(settings.LIQ_DB) == os.path.abspath(DEFAULT_DB):
        print("Refusing to import into the live DB; set LIQ_DB")
        sys.exit(1)
    if len(sys.argv) != 2:
        print("Usage: liq-import <file.jsonl>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    conn = db.connect()
    n_msgs = n_liq = n_skip = 0
    last_id = (db.get_sync_state(conn) or {}).get("last_msg_id") or 0
    with open(path, encoding="utf-8") as f:
        for file_line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                msg_id = int(msg["id"])
                ts = int(datetime.fromisoformat(msg["date_utc7"]).timestamp())
                text = msg.get("text")
            except (ValueError, KeyError, TypeError) as e:
                print(f"{path}:{file_line_no}: skipped malformed line ({type(e).__name__}: {e})", file=sys.stderr)
                continue
            rows, skipped = parse_message(msg_id, ts, text)
            n_liq += db.insert_liquidations(conn, rows)
            n_skip += db.insert_skipped(conn, skipped)
            n_msgs += 1
            last_id = max(last_id, msg_id)
    summary = summary_text(n_msgs, n_liq, n_skip)
    db.set_sync_state(conn, last_msg_id=last_id, last_sync_utc=int(time.time()), last_summary=summary)
    conn.commit()
    print(summary)


def login_main():
    """liq-login: one-time interactive Telegram login, writes liqdash.session."""
    from liqdash import telegram_sync

    telegram_sync.login()


def sync_main():
    """liq-sync: fetch new channel messages since the last sync."""
    from liqdash import telegram_sync

    print(telegram_sync.sync())
