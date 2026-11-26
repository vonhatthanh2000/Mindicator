# Progress: Binance Liquidation Dashboard

Status: implement 02 · awaiting user · next: harden 02 · updated 2026-11-26
Base: none (not a git repo; project started empty except plans/idea.md and tasks/)

## Sub-tasks
- 01 Parser and local database: hardened (files: pyproject.toml, uv.lock, .gitignore, .env.example, liqdash/{__init__,config,parser,db,cli}.py, tests/{test_parser,test_db,test_config_cli}.py, tests/fixtures/samples.jsonl)
- 02 Telegram login and sync: MVP v1 awaiting confirm (user must run How to verify)
- 03 Binance market data: not started
- 04 Summary metrics and API: not started
- 05 Dashboard: sync, cards and leaderboard: not started
- 06 Long/short chart and heatmap: not started
- 07 Token detail panel: not started
- 08 Signal badges: not started

## Done
- [x] 02 task 1: created liqdash/telegram_sync.py (login, sync)
- [x] 02 task 2: edited liqdash/cli.py (login_main, sync_main; summary_text moved to telegram_sync), edited pyproject.toml (liq-login, liq-sync scripts)
## In progress
## Next
- User fills .env, runs 02 How to verify, then confirms

## Checkpoint
- Sub-task: 02 · MVP v1
- Command: `uv run liq-login` then `uv run liq-sync` twice (live DB, `LIQ_DB` unset)
- Result: not run by the agent: needs the user's Telegram credentials and login code. Offline checks done: imports OK, 01 How to verify unchanged, 29 tests pass, missing `.env` key fails before the DB is touched.
- Hardcoded / faked: channel `BinanceLiquidations` and session name `liqdash` are constants; no not-logged-in guard (an unauthorized `liq-sync` would prompt for a phone login interactively, H1); a missing `.env` key shows a Python traceback naming the key; progress_cb gets `None` as the estimate (H5); no lock (H6), no mark-as-read (H3), no network-error handling (H4)
- Check script: none
## Gotchas
- Required `.env` keys are fetched with `settings.require("TG_API_ID", …)` (raises `ConfigError` naming the key); call it only inside commands that need them.
- About 15% of channel lines are TradFi tickers (XAU, CL, SOXL, MSTR, …). They are classified from Binance exchangeInfo `contractType == TRADIFI_PERPETUAL`.
- Binance 1d klines cut at UTC midnight, so use 1h klines for UTC+7 days.
- Channel minimum looks like about $50K (smallest of 40 samples: $50.7K). The sample had no M/B sizes and no multi-line posts; the synthetic fixture lines cover those.

## History
2026-11-25 · plan · pivotal confirmed: Telethon with the user's own account (not the t.me/s web page, not a bot)
2026-11-25 · plan · pivotal confirmed: per-day Binance candle data for volume/price instead of sync-time snapshots; refined to 1h candles for UTC+7 day edges (pending user OK)
2026-11-25 · plan · scope: full idea.md build, local only, crypto tokens only (TradFi stored but hidden), mark-as-read off by default, 30-day lookback
2026-11-25 · plan · plan written: 8 sub-tasks (PLAN.md, TASK.md, PIVOTAL.md, samples.jsonl fixture from 40 real channel posts)
2026-11-25 · review · 4 blocking found: fixture import would pollute the live DB and skip the first-sync lookback; sqlite3 CLI missing; 04 verify needed symbols classified first; login rule blocked offline commands
2026-11-25 · review · PLAN.md fixed: LIQ_DB + live-DB guard, sync = Telegram then market with cross-process lock, closed-klines-only and 29-day OI clamp, weight budgeting, summary Market suffix, non-ASCII token regex, avg_prior coverage rule, signal null rules, funding only for current period, exact verify outputs for 01/03/04/06/08 recomputed from the fixture
2026-11-25 · review · open items for user (recommended defaults written into PLAN.md pending OK): U1 CLUSTER needs ≥5 liqs and ≥$500K; U2 hourly candles (pivotal #2); U3 Sync button also fetches market data; U4 no SPIKE without history; U5 partial week scales avg_prior pro rata
2026-11-25 · review · user confirmed U1–U5 as recommended (CLUSTER ≥5 liqs & ≥$500K, hourly candles, Sync includes market data, no SPIKE without history, partial week pro rata); pivotal #2 confirmed; no PLAN.md text change needed
2026-11-26 · review · plan approved (user ran /justdev implement)
2026-11-26 · implement · MVP v1 confirmed (01)
