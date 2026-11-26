# Deviations

## 01 MVP
- **Only `liq-import` is registered in `pyproject.toml` `[project.scripts]` so far.** Why: the other scripts (`liq-login`, `liq-sync`, `liq-market`, `liq-serve`) point at functions that their own sub-tasks (02–04) create; registering them now would give broken commands. Impact: each later sub-task adds its script line.
- **`.gitignore` also lists `*.session-journal`, `__pycache__/` and `*.pyc`.** Why: Telethon writes a journal file next to the session, and Python bytecode shouldn't be committed. Impact: none on behavior.
- **`.env.example` threshold keys are named** `SPIKE_MULT`, `SPIKE_MIN_USD`, `SIDE_SHARE`, `FLUSH_MIN_USD`, `STREAK_DAYS`, `CLUSTER_BAND_PCT`, `CLUSTER_MIN_COUNT`, `CLUSTER_MIN_SHARE`, `CLUSTER_MIN_USD` (PLAN.md gave values, not names). Impact: 08 reads these names from `Settings`.

## 01 harden
- **Config validation is `Settings.require(*keys)` raising `ConfigError("Missing required setting <KEY> in .env")`**, called lazily by the commands that need the keys (H3 left the mechanism open). Impact: 02 calls `settings.require("TG_API_ID", "TG_API_HASH", "TG_PHONE")` in `liq-login`/`liq-sync`.
- **`liq-import` with a wrong number of arguments prints `Usage: liq-import <file.jsonl>` and exits 2.** Malformed lines print `<file>:<line>: skipped malformed line (...)` to stderr and don't count as messages.
- **Extra spec file `tests/test_config_cli.py`** (config `require`, malformed JSONL, live-DB guard). PLAN.md's test scope names only test_parser/test_db for 01; this covers H3/H4 and the 01 live-DB acceptance criterion.

## 02 MVP
- **`summary_text()` now lives in `liqdash/telegram_sync.py`**; `cli.py` imports it. Why: one definition for import and sync. Impact: none on output.
- **An empty first sync (0 messages in the lookback) leaves `last_msg_id` NULL.** Why: otherwise the next sync would use `min_id=0` and pull the whole channel history. Impact: the next sync is treated as a first sync again (`first_sync_utc` is reset to the new lookback start).
- **Messages are parsed from `msg.message` (raw text), not `msg.text`.** Why: `msg.text` is Telethon's markdown-formatted text and can wrap the emoji in `**`. Impact: the parser sees the plain channel text.
