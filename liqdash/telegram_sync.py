import asyncio
import time
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient

from liqdash import db
from liqdash.config import settings
from liqdash.parser import parse_message

CHANNEL = "BinanceLiquidations"
SESSION = "liqdash"  # Telethon appends .session -> liqdash.session
BATCH = 500


def summary_text(n_msgs, n_liq, n_skip):
    return f"Synced {n_msgs} messages → {n_liq} liquidations, {n_skip} skipped lines."


def _client():
    api_id, api_hash = settings.require("TG_API_ID", "TG_API_HASH")
    return TelegramClient(SESSION, int(api_id), api_hash)


def login():
    (phone,) = settings.require("TG_PHONE")

    async def run():
        client = _client()
        await client.start(phone=phone)  # prompts for the code and 2FA password in the terminal
        me = await client.get_me()
        print(f"Logged in as {me.first_name}")
        await client.disconnect()

    asyncio.run(run())


async def _sync(progress_cb=None):
    client = _client()  # validates .env before touching the DB
    conn = db.connect()
    state = db.get_sync_state(conn) or {}
    last_id = state.get("last_msg_id")
    if last_id is None:
        start = datetime.now(timezone.utc) - timedelta(days=settings.LOOKBACK_DAYS)
        db.set_sync_state(conn, first_sync_utc=int(start.timestamp()))
        conn.commit()
        kwargs = {"offset_date": start}
        last_id = 0
    else:
        kwargs = {"min_id": last_id}

    n_msgs = n_liq = n_skip = 0
    await client.start()
    try:
        async for msg in client.iter_messages(CHANNEL, reverse=True, **kwargs):
            rows, skipped = parse_message(msg.id, int(msg.date.timestamp()), msg.message)
            n_liq += db.insert_liquidations(conn, rows)
            n_skip += db.insert_skipped(conn, skipped)
            n_msgs += 1
            last_id = max(last_id, msg.id)
            if n_msgs % BATCH == 0:
                db.set_sync_state(conn, last_msg_id=last_id)
                conn.commit()
                if progress_cb:
                    progress_cb(n_msgs, None)
    finally:
        await client.disconnect()

    summary = summary_text(n_msgs, n_liq, n_skip)
    if last_id:  # keep NULL after an empty first sync, so the next one still uses the lookback
        db.set_sync_state(conn, last_msg_id=last_id)
    db.set_sync_state(conn, last_sync_utc=int(time.time()), last_summary=summary)
    conn.commit()
    return summary


def sync(progress_cb=None):
    return asyncio.run(_sync(progress_cb))
