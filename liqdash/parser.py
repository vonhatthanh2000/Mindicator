import logging
import re

log = logging.getLogger(__name__)

LINE_RE = re.compile(
    r"^(🔴|🟢)?\s*#(\S+?)\s+Liquidated\s+(Long|Short):\s+"
    r"\$([0-9]+(?:\.[0-9]+)?)([KMB]?)\s+at\s+\$([0-9]+(?:\.[0-9]+)?)$"
)
MULT = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}
EMOJI_SIDE = {"🔴": "Long", "🟢": "Short"}


def parse_message(msg_id, ts_utc, text):
    """Split a message into liquidation rows and skipped lines.

    rows:    (msg_id, line_no, ts_utc, token, side, size_usd, price_text)
    skipped: (msg_id, line_no, ts_utc, raw)
    """
    rows, skipped = [], []
    lines = [ln.strip() for ln in (text or "").split("\n")]
    lines = [ln for ln in lines if ln]
    for line_no, line in enumerate(lines):
        m = LINE_RE.match(line)
        if not m:
            skipped.append((msg_id, line_no, ts_utc, line))
            continue
        emoji, token, side, size, unit, price = m.groups()
        if emoji and EMOJI_SIDE[emoji] != side:
            log.warning("emoji/side mismatch in msg %s line %s: %r", msg_id, line_no, line)
        size_usd = round(float(size) * MULT[unit])
        rows.append((msg_id, line_no, ts_utc, token, side, size_usd, price))
    return rows, skipped
