# Binance Liquidation Dashboard

## Goal
A local dashboard where pressing **Sync** pulls every new message from t.me/BinanceLiquidations plus Binance market data, and which shows daily and weekly per-token liquidation recaps (long vs short), ranked by liquidations relative to Binance volume, with signal badges. Background: `plans/idea.md`; this file overrides it wherever they differ.

## Non-goals
- Hosting, a dashboard password, timer-based sync, push alerts, watchlist, CSV export, React.
- The Binance liquidation websocket as a data source.
- Showing non-crypto (TradFi) tickers anywhere in the UI or in metrics.
- Git operations: the folder is not a git repo, and the user handles git.

## Decisions
- **Config:** `liqdash/config.py` reads `.env` (python-dotenv) into a `Settings` object with defaults: `TG_API_ID`, `TG_API_HASH`, `TG_PHONE` (no default), `TIMEZONE=Asia/Saigon`, `LOOKBACK_DAYS=30`, `MARK_AS_READ=false`, `LIQ_DB=liquidations.db`, plus the signal thresholds listed under Signals. `SYMBOL_OVERRIDES: dict[str,str] = {}` lives in the same file.
- **DB path:** every command uses `Settings.LIQ_DB`. Every fixture-based How to verify runs with `LIQ_DB=fixture.db`, after deleting it first. `liq-import` exits non-zero with `"Refusing to import into the live DB; set LIQ_DB"` when `LIQ_DB` resolves to the default `liquidations.db`, so synthetic rows can never reach real data or set the real `last_msg_id`.
- **Telegram source:** Telethon logged in as the user's own account (pivotal #1). Never use a bot or the `t.me/s/` web page.
- **Login** is a one-time terminal command `uv run liq-login` (phone, code, 2FA), which writes the session file `liqdash.session` in the project root. Only `liq-sync` and `POST /api/sync` need it: they fail fast with `"Not logged in: run 'uv run liq-login' first"` when the file is missing or not authorized. Check that the file exists *before* building a `TelegramClient`, because Telethon creates the file on construction. `liq-import`, `liq-market` and `liq-serve` need neither the session nor the `TG_*` keys.
- **Sync = Telegram, then market data.** `liq-sync` and `POST /api/sync` both run the Telegram sync and then the Binance market fetch. A market-data failure never undoes or fails the Telegram part.
- **Sync position:** the app keeps its own `sync_state.last_msg_id` and never relies on Telegram's read marker. Fetch with `client.iter_messages(channel, min_id=last_msg_id, reverse=True)`. On the first sync (no state), use `offset_date = now - LOOKBACK_DAYS` with `reverse=True`. Commit rows and `last_msg_id` together every 500 messages. A message with no text (media or service) yields 0 lines but still advances `last_msg_id`. Store `sync_state.first_sync_utc` (the lookback start) on the first sync; it defines **coverage start**.
- **Sync concurrency:** a cross-process lock file `sync.lock` (`fcntl.flock`, non-blocking) guards every sync, CLI or UI. If it is held, the CLI prints `already running` and exits 1, and the API returns `{"started": false, "reason": "already running"}`. The API sync runs in a background thread that calls `asyncio.run(...)` and creates its `TelegramClient` inside that loop. SQLite is opened in WAL mode with one connection per thread.
- **Mark as read:** off by default. When `MARK_AS_READ=true`, call `client.send_read_acknowledge(channel, max_id=last_msg_id)` after a successful Telegram sync.
- **Parsing:** one liquidation per line; a message is split on `\n`. Regex (full match, after strip): `^(🔴|🟢)?\s*#(\S+?)\s+Liquidated\s+(Long|Short):\s+\$([0-9]+(?:\.[0-9]+)?)([KMB]?)\s+at\s+\$([0-9]+(?:\.[0-9]+)?)$`. `\S+?` (not `[A-Z0-9]+`) is deliberate, because Binance lists non-ASCII perpetuals such as `币安人生`. The side word is the source of truth. When the emoji disagrees (🔴 should be Long, 🟢 Short), keep the row and log a warning. Size → integer USD (`round(float*mult)`, K=1e3, M=1e6, B=1e9). Price is stored as the exact TEXT from the message. Tokens are kept as written (`1000PEPE`, `1INCH`). A line that doesn't match goes into `skipped_lines` and never fails the sync. Empty lines are ignored and not counted. `line_no` is the 0-based index among non-empty lines.
- **Price arithmetic** (min/max, clusters) always uses `float(price)` in Python, never SQL aggregates on the TEXT column.
- **Dedup key:** `(msg_id, line_no)` primary key, inserted with `INSERT OR IGNORE`.
- **Sync summary text:** `Synced N messages → M liquidations, S skipped lines.` N = messages read; M and S = rows newly inserted. When the market fetch ran, append ` Market: U tokens updated, F failed (TOK1, TOK2…).`, with ` F failed (…)` omitted when F = 0. The text is saved in `sync_state.last_summary`.
- **Time:** store `ts_utc` as integer epoch seconds. All day and week bucketing uses `TIMEZONE` via `zoneinfo`. A day is local 00:00 to 24:00, and a week runs Monday 00:00 to the next Monday 00:00 local. Query by computed `[start_utc, end_utc)` ranges, never by SQL date functions. The importer reads `date_utc7` with `datetime.fromisoformat` and respects its own offset.
- **Crypto only:** store every parsed line. Metrics and UI include a token only if its `symbols` row has `is_crypto = 1`. A token with no `symbols` row is not yet classified and is excluded. A row with `symbol NULL` (looked up, not found on Binance) has `is_crypto = 1` and shows `"no volume data"`. `is_crypto = 0` exactly when the mapped exchangeInfo symbol has `contractType == "TRADIFI_PERPETUAL"`.
- **Symbol mapping:** `SYMBOL_OVERRIDES.get(token, token + "USDT")`, looked up in `GET https://fapi.binance.com/fapi/v1/exchangeInfo`. The result is saved in the `symbols` table for every token with liquidations, refreshed on every market fetch.
- **Market data (pivotal #2), 1h klines** (`/fapi/v1/klines?interval=1h&limit=1000`), summed into local days and weeks. Do not use 1d klines (they cut days at UTC midnight).
  - **Kline range:** for each crypto token with a symbol, fetch one continuous run of **closed** klines (`close_time < now`). It starts at the later of local Monday 00:00 of the week holding the token's earliest stored liquidation and `coverage start − 28 days` (so `avg_prior` has history), and ends at the last closed hour. Fetch only hours after the token's newest stored `open_time_utc`.
  - **Per period:** `volume_usd` = sum of `quote_volume` over the period's hours; `price_change_pct` = last close / first open − 1 over those hours; `null` if no klines cover the period.
  - **Open interest:** `/futures/data/openInterestHist?period=1h&limit=500`, with `startTime` clamped to `now − 29 days`, paged. Store the last `sumOpenInterestValue` of each local day in `oi_daily`. Each fetch re-fetches from the start of the current local day and overwrites today's row. Days with no data get `oi_usd = null`. `oi_usd` for a period = its last day's value; `oi_change_pct` = vs the previous period's last-day value.
  - **Funding:** `/fapi/v1/premiumIndex` (one call, all symbols) → `lastFundingRate`, saved per fetch in `market_snapshots`. `funding_rate` = the latest snapshot value, set only when the selected period contains now; otherwise `null`.
- **Binance rate limiting:** requests are sequential (httpx). Read `X-MBX-USED-WEIGHT-1M` on every response and sleep until the next minute when it passes 2000. On 429/418, sleep `Retry-After` seconds and retry (at most 3 times). Any other HTTP error, or exhausted retries, marks that token failed for this fetch and moves on.
- **Calculations happen on request** from stored rows. No precomputed aggregate tables.
- **Metrics per crypto token per period:** long_usd, short_usd, total_usd, count, long_short_ratio (long/short; `null` if short = 0), max_single_usd, price_min, price_max, avg_prior, change_vs_avg (total/avg_prior − 1; `null` if avg_prior is null or 0), liq_to_volume (total/volume_usd; `null` without volume), volume_usd, price_change_pct, oi_usd, oi_change_pct, funding_rate.
- **avg_prior:** day view = mean daily total over the 7 previous local days; week view = mean weekly total over the 4 previous weeks. Count only periods that lie entirely on or after the local day of coverage start; a covered period with no rows counts as 0. `null` if no prior period is covered. **Partial current week:** when the selected week contains now, multiply avg_prior by (elapsed hours of the week / 168) before comparing.
- **Ranking and filters:** sort by `liq_to_volume` descending, with tokens that have no volume data last. `min_total` filters on `total_usd`. When `min_volume` > 0, tokens with no volume data are excluded. Totals (`long_usd`, `short_usd`, `active_tokens`, `biggest`, `smallest`) are computed over the filtered crypto set.
- **Signals** (thresholds in `.env` with these defaults). "Share" = side_usd / total_usd of that token for that local day. Week view = the union of the badges over the week's local days up to today.
  - `SPIKE`: avg_prior (7 days) > 0, day total ≥ 3 × avg_prior and ≥ $500K. A token with no covered history never gets SPIKE.
  - `LONG_FLUSH`: long share ≥ 70%, total ≥ $1M, price_change_pct < 0. Doesn't fire when price_change_pct is null.
  - `SHORT_SQUEEZE`: short share ≥ 70%, total ≥ $1M, price_change_pct > 0. Doesn't fire when price_change_pct is null.
  - `ONE_SIDED_STREAK`: the same side has ≥ 70% share on ≥ 3 consecutive local days ending on the selected day. A day with no liquidations for the token breaks the streak.
  - `CLUSTER`: some ±0.5% price band (centered on each liquidation price of the day; the best band by USD wins, ties go to the lower price) holds ≥ 5 liquidations, ≥ 30% of the token's day USD, and ≥ $500K. Report the band's center price, its count and its share.
- **Stack:** Python 3.12, `uv`, `pyproject.toml` with scripts `liq-login`, `liq-sync`, `liq-import`, `liq-market`, `liq-serve`; Telethon, FastAPI + uvicorn, httpx, python-dotenv; stdlib `sqlite3` (no ORM); pytest. The `sqlite3` CLI is not installed, so checks query via Python.
- **Server:** `liq-serve` runs uvicorn on `127.0.0.1:8000` only. No auth.
- **Sync from the UI:** `POST /api/sync` → `{"started": true}` or `{"started": false, "reason": "already running"}`. `GET /api/sync/status` → `{running, phase: "telegram"|"market"|null, fetched, estimated_total, inserted, skipped, error, finished_at, summary}`. The page polls it every 1s while running. A not-logged-in sync ends at once with `error` set to the login message.
- **Frontend:** one `liqdash/static/index.html` with vanilla JS and Apache ECharts from cdnjs (pinned version), served by FastAPI at `/`. No build step.

## Constraints
- Never log or print `TG_API_HASH`, the phone number or the session contents. `.env`, `*.session`, `*.db`, `*.db-wal`, `*.db-shm`, `sync.lock` and `.venv/` go in `.gitignore`.
- Telegram is used read-only (plus the optional read-ack); nothing is sent. Binance endpoints are public and need no key. No paid services.
- Telegram pacing: rely on Telethon's default flood-wait sleep. Make no parallel requests. `iter_messages` sleeps about 1s between pages on large pulls, so a 30-day first sync (~17K messages, ~170 pages) takes about 3+ minutes. That is expected.
- No test may call real Telegram or Binance.

## Data model (`Settings.LIQ_DB`)
- `liquidations(msg_id INT, line_no INT, ts_utc INT, token TEXT, side TEXT CHECK(side IN('Long','Short')), size_usd INT, price TEXT, PRIMARY KEY(msg_id,line_no))`, index on `(token, ts_utc)` and `(ts_utc)`.
- `skipped_lines(msg_id INT, line_no INT, ts_utc INT, raw TEXT, PRIMARY KEY(msg_id,line_no))`.
- `sync_state(id INT PRIMARY KEY CHECK(id=1), last_msg_id INT, first_sync_utc INT, last_sync_utc INT, last_summary TEXT)`.
- `symbols(token TEXT PRIMARY KEY, symbol TEXT NULL, contract_type TEXT NULL, is_crypto INT, updated_utc INT)`.
- `klines_1h(symbol TEXT, open_time_utc INT, open TEXT, close TEXT, quote_volume REAL, PRIMARY KEY(symbol, open_time_utc))`.
- `oi_daily(symbol TEXT, day TEXT, oi_usd REAL NULL, PRIMARY KEY(symbol, day))` (day = local `YYYY-MM-DD`).
- `market_snapshots(sync_utc INT, symbol TEXT, funding_rate REAL, mark_price TEXT, PRIMARY KEY(sync_utc, symbol))`.

Reference input: `tasks/2026-11-25-liquidation-dashboard/samples.jsonl` holds 40 real channel messages (IDs 416203–416242) plus 3 synthetic ones (IDs 416300–416302): a 2-line message with `$1.2M`/`$1.05B`/`1000PEPE`, a `1INCH` line and an ad line. That is 43 messages and 44 non-empty lines, which parse into 43 liquidations plus 1 skipped. All are dated 2026-11-25 local. Tokens: crypto BTC(16) ETH(6) SOL(3) ZEC FIL 1000PEPE 1INCH; TradFi XAU CL SOXL SOXS MSTR SNDK SKHYNIX KORU SNXX.

## 01 – Parser and local database
### MVP
- [x] 1. `pyproject.toml` (uv, deps, scripts), `.gitignore`, `.env.example` (all Settings keys), minimal `liqdash/config.py` (the `Settings` and `SYMBOL_OVERRIDES` from Decisions, plain getenv with defaults).
- [x] 2. `liqdash/parser.py`: `parse_message(msg_id, ts_utc, text) -> (rows, skipped)` per the Parsing decision.
- [x] 3. `liqdash/db.py`: `connect()` (WAL) creates every table in the Data model, plus `insert_liquidations`, `insert_skipped`, `get/set_sync_state`.
- [x] 4. `liqdash/cli.py` `liq-import <jsonl>`: read `{id, date_utc7, text}` lines, parse, insert, set `last_msg_id`, print the summary text (live-DB guard per Decisions). Copy `samples.jsonl` to `tests/fixtures/samples.jsonl`.

**How to verify:**
```
rm -f fixture.db*; export LIQ_DB=fixture.db
uv run liq-import tests/fixtures/samples.jsonl && uv run liq-import tests/fixtures/samples.jsonl
uv run python -c "import sqlite3;[print('|'.join(map(str,r))) for r in sqlite3.connect('fixture.db').execute(\"select token,side,size_usd,price from liquidations where token in ('1000PEPE','BTC') order by size_usd desc limit 2\")]"
LIQ_DB= uv run liq-import tests/fixtures/samples.jsonl; echo "exit=$?"
```
Expected:
```
Synced 43 messages → 43 liquidations, 1 skipped lines.
Synced 43 messages → 0 liquidations, 0 skipped lines.
BTC|Short|1050000000|59500.00
1000PEPE|Long|1200000|0.00001234
Refusing to import into the live DB; set LIQ_DB
exit=1
```

### Hardening backlog
- [x] H1. Spec `tests/test_parser.py`: K/M/B and decimal sizes, digit-leading tokens, a non-ASCII token (`#币安人生`), full-precision price text, multi-line message line numbering, empty lines ignored, a message with no text (0 lines), ad line skipped, emoji/side mismatch keeps the side word and logs a warning, trailing spaces.
- [x] H2. Spec `tests/test_db.py`: dedup on rerun (0 new), skipped lines also deduped, schema creation is idempotent.
- [x] H3. `config.py` validation: a missing required key raises an error naming the key, only when a command that needs it runs.
- [x] H4. Malformed JSONL input in `liq-import` reports the line number and continues.

## 02 – Telegram login and sync
### MVP
- [x] 1. `liqdash/telegram_sync.py`: `login()` (interactive, writes `liqdash.session`, prints `Logged in as <first name>`) and `sync(progress_cb=None) -> summary` per the Decisions (session check, min_id / first-sync lookback, reverse order, batch commit every 500, `first_sync_utc`, uses the parser and db).
- [x] 2. `liq-login` and `liq-sync` scripts in `liqdash/cli.py` (in this sub-task `liq-sync` runs the Telegram part only; 03 adds market data).

**How to verify:** (the user runs this with `.env` filled, on the live DB, which no fixture has ever touched) `uv run liq-login`, then `uv run liq-sync`, then `uv run liq-sync` again.
Expected: login prints `Logged in as <name>`. The first sync takes about 3+ minutes and prints `Synced N messages → M liquidations, S skipped lines.` with N in the thousands. The second prints `Synced 0 messages → 0 liquidations, 0 skipped lines.` (or only the messages posted in between).

### Hardening backlog
- [ ] H1. Not-logged-in guard (message and the check-before-construct rule in Decisions); `liq-sync` exits 1.
- [ ] H2. Resume after interruption: kill mid-sync, rerun, no gaps or duplicates.
- [ ] H3. `MARK_AS_READ` per Decisions.
- [ ] H4. Network errors end the sync with `error` set and the committed progress kept.
- [ ] H5. `progress_cb(fetched, estimated_total)`; estimate = latest channel msg id − `last_msg_id` (first sync: latest id − id of the first message in the lookback window).
- [ ] H6. `sync.lock` cross-process guard per Decisions.
- [ ] H7. Spec `tests/test_sync.py` with a fake Telethon client (async iterator of fake messages): first sync sets `first_sync_utc`, incremental sync, a multi-line message, a text-less message advances `last_msg_id`, a resume, lock held → `already running`.

## 03 – Binance market data
### MVP
- [ ] 1. `liqdash/binance.py`: refresh `symbols` from exchangeInfo (mapping and is_crypto per Decisions) and fetch closed 1h klines per the Kline range decision.
- [ ] 2. `liq-market` script: run it and print one line per token, `TOKEN SYMBOL crypto klines=<n>` or `TOKEN SYMBOL tradfi (hidden)` or `TOKEN - crypto (no volume data)`. `liq-sync` calls the same function after the Telegram part.

**How to verify:**
```
rm -f fixture.db*; export LIQ_DB=fixture.db
uv run liq-import tests/fixtures/samples.jsonl && uv run liq-market
```
Expected: 16 lines (order may vary, klines counts vary): `BTC BTCUSDT crypto klines=…`, the same for ETH, SOL, ZEC, FIL, 1000PEPE, 1INCH (each `<TOKEN>USDT crypto`); and `XAU XAUUSDT tradfi (hidden)`, the same for CL, SOXL, SOXS, MSTR, SNDK, SKHYNIX, KORU, SNXX. A second `uv run liq-market` makes no kline requests except for hours closed since the first run.

### Hardening backlog
- [ ] H1. Rate limiting and retries per the Binance rate-limiting decision; failed tokens are listed in the summary's ` Market:` suffix and never fail the Telegram part.
- [ ] H2. `SYMBOL_OVERRIDES` applied; a token not on Binance is stored with `symbol NULL, is_crypto 1`.
- [ ] H3. Open interest per Decisions (29-day clamp, paging, today's row overwritten).
- [ ] H4. Funding via premiumIndex into `market_snapshots`.
- [ ] H5. Spec `tests/test_binance.py` with mocked httpx: exchangeInfo classification, kline paging past 1000 rows, only closed klines stored, OI local-day selection and 29-day clamp, 429 → Retry-After → retry, weight-header pause.

## 04 – Summary metrics and API
### MVP
- [ ] 1. `liqdash/metrics.py`: `period_bounds(period, date, tz)` and `summary(period, date, min_volume, min_total)` returning per-token metrics (every field in Decisions) for crypto tokens plus totals: long_usd, short_usd, active_tokens, biggest single liquidation (token, size, price, time), smallest size seen in the period.
- [ ] 2. `liqdash/api.py` (FastAPI): `GET /api/summary?period=day|week&date=YYYY-MM-DD&min_volume=&min_total=` and `GET /api/status` (last sync time, last summary, liquidation count, skipped count of the last sync and in total, smallest crypto size ever seen). `liq-serve` script.

**How to verify:**
```
rm -f fixture.db*; export LIQ_DB=fixture.db
uv run liq-import tests/fixtures/samples.jsonl && uv run liq-market
(uv run liq-serve &) ; sleep 3
curl -s 'localhost:8000/api/summary?period=day&date=2026-11-25' | python3 -m json.tool | head -60
```
Expected:
- `totals.active_tokens` = 7, `totals.long_usd` = 2445200, `totals.short_usd` = 1051468600, `totals.smallest` = 55700.
- No XAU/SOXL/etc.
- BTC `count` = 16 and `max_single_usd` = 1050000000.
- Every token has a non-null `volume_usd`, and the list is sorted by `liq_to_volume` descending.

### Hardening backlog
- [ ] H1. Spec `tests/test_metrics.py`:
  - Local day edges: a liquidation at 23:59:59 and one at 00:00:00 land on different days.
  - The week starts on Monday.
  - avg_prior coverage rule and the partial-week scaling.
  - The null cases for ratio, change_vs_avg and funding outside the current period.
  - Unclassified and TradFi tokens are excluded.
  - Both filters, including `min_volume` dropping no-volume tokens.
- [ ] H2. Input validation: a bad period or date → 422 with a message.
- [ ] H3. Period volume/price/OI aggregation from `klines_1h` and `oi_daily` with fake rows (covered by the H1 spec file).

## 05 – Dashboard: sync, cards and leaderboard
### MVP
- [ ] 1. `POST /api/sync` + `GET /api/sync/status` per the Sync from the UI decision (background thread, the lock, Telegram then market, `phase`).
- [ ] 2. `liqdash/static/index.html` served at `/`:
  - Top bar: Sync button with live progress text, last sync time, a Day/Week toggle, and a date picker that defaults to today in `TIMEZONE`.
  - Summary cards: total long vs short, active tokens, biggest single liquidation, smallest size seen.
  - Leaderboard table: one row per token with every metric, sortable by clicking a column header, with min volume and min total filters.

**How to verify:** first `curl -s -XPOST localhost:8000/api/sync; curl -s -XPOST localhost:8000/api/sync` (the second returns `"reason": "already running"`). Then open `http://localhost:8000` and press Sync.
Expected: the progress text counts up through the Telegram and then the market phase, then shows the summary text. The cards and table fill for today. Switching to Week reloads. Sorting and filters work. No TradFi tickers appear.

### Hardening backlog
- [ ] H1. Spec `tests/test_api_sync.py`: a second POST while running → `already running`; a not-logged-in sync → status `error` with the login message.
- [ ] H2. Empty states (no data for the date, never synced); a status-poll failure shown in the UI.
- [ ] H3. Number formatting ($1.2M, %), "no volume data" cells, period and filters remembered in `localStorage` (wrapped in try/catch).

## 06 – Long/short chart and heatmap
### MVP
- [ ] 1. A long-vs-short horizontal bar chart (ECharts) of the top 15 filtered tokens by total: longs to the left in red, shorts to the right in green.
- [ ] 2. `GET /api/heatmap?week=YYYY-MM-DD` (any date in the week, normalized to its local Monday): crypto tokens × 7 local days of total USD, the top 30 tokens by week total, zero-filled. A heatmap appears in week view.

**How to verify:** `curl -s 'localhost:8000/api/heatmap?week=2026-11-26' | python3 -m json.tool | head -20` on the fixture DB (from 04). Then, after a real sync, open the dashboard and switch to Week.
Expected: the curl shows `days` from 2026-11-23 to 2026-11-29; BTC's 2026-11-25 cell = 1051599600 (sum of the 16 BTC sizes); other days are 0. In the UI, 15 tokens are split left and right; the heatmap has Mon–Sun columns, darker for bigger days, and hovering shows exact $ values.

### Hardening backlog
- [ ] H1. Spec for the heatmap endpoint (day bucketing, Monday normalization, top-30 cut, zero-filled cells).
- [ ] H2. Charts update on period, date or filter change without a reload; readable in dark and light.

## 07 – Token detail panel
### MVP
- [ ] 1. `GET /api/token/{token}?period=&date=` returns:
  - The liquidation list over time (ts, side, size, price).
  - Hourly long/short totals.
  - Price-level clusters: ±0.5% bands ranked by USD, the top 5, using the CLUSTER band rule without the badge thresholds.
  - That token's metrics.
- [ ] 2. Clicking a leaderboard row opens a side panel: a timeline chart (hourly long/short bars, with the liquidation prices as dots) and a top-5 cluster table.

**How to verify:** `curl -s 'localhost:8000/api/token/BTC?period=day&date=2026-11-25' | python3 -m json.tool | head -30` on the fixture DB, then click BTC in the UI.
Expected: 16 BTC liquidations; the top cluster band contains 59500.00 (the synthetic $1.05B line); the panel shows the chart and the table.

### Hardening backlog
- [ ] H1. Spec for the cluster algorithm (best ±0.5% band, the lower-price tie rule, a single liquidation).
- [ ] H2. An unknown, unclassified or TradFi token → 404; the panel closes with Esc or a click outside.

## 08 – Signal badges
### MVP
- [ ] 1. `liqdash/signals.py` computing SPIKE, LONG_FLUSH, SHORT_SQUEEZE, ONE_SIDED_STREAK and CLUSTER per Decisions; a `signals` list (`{code, reason}`) added to each token in `/api/summary`; `python -m liqdash.signals --period --date` prints them.
- [ ] 2. Badges next to each token in the leaderboard, with a hover tooltip showing the reason; a "not financial advice" footer line.

**How to verify:**
```
rm -f fixture.db*; export LIQ_DB=fixture.db
uv run liq-import tests/fixtures/samples.jsonl && uv run liq-market
uv run python -m liqdash.signals --period day --date 2026-11-25
```
Expected: exactly two CLUSTER lines: `BTC: CLUSTER (14 liquidations, 100% within ±0.5% of 59207.50)` and `ETH: CLUSTER (5 liquidations, 90% within ±0.5% of 1633.72)`. No SPIKE or ONE_SIDED_STREAK anywhere, because there is no covered history. LONG_FLUSH or SHORT_SQUEEZE may also appear for BTC, depending on the live price move.

### Hardening backlog
- [ ] H1. Spec `tests/test_signals.py` with synthetic rows at, just above and just below each threshold, plus the null and no-history cases from Decisions.
- [ ] H2. Thresholds loaded via config (Decisions).

## Acceptance criteria
- 01: With `LIQ_DB=fixture.db`, importing the fixture twice gives 43 liquidations then 0, with 1 skipped line. `$1.05B` → 1050000000, and price `0.00001234` is kept as text.
- 01: `liq-import` refuses the default live DB and exits 1.
- 01: A line that doesn't parse is stored in `skipped_lines` and the import still succeeds.
- 02: Without `liqdash.session`, `liq-sync` exits non-zero with `Not logged in: run 'uv run liq-login' first`, and no session file is created.
- 02: The first sync covers `LOOKBACK_DAYS`. A repeated sync with no new posts inserts 0. An interrupted sync, resumed later, leaves no gaps or duplicates.
- 02: With `MARK_AS_READ` unset, the channel's read state is not changed.
- 02: A second concurrent sync (CLI or API) reports `already running`.
- 03: XAU, CL, SOXL, SOXS, MSTR, SNDK, SKHYNIX, KORU and SNXX are classified TradFi. BTC, ETH, SOL, ZEC, FIL, 1000PEPE and 1INCH are crypto. A token not on Binance is crypto with no symbol.
- 03: Only closed 1h klines are stored. A Binance failure does not fail the Telegram sync and is listed in the summary's ` Market:` suffix.
- 04: Day boundaries follow `TIMEZONE`, and weeks start on Monday. A day's volume is the sum of the 24 hourly candles of that local day.
- 04: `/api/summary` never contains TradFi or unclassified tokens. Ranking is `liq_to_volume` descending with nulls last.
- 05: The server listens on 127.0.0.1 only.
- 06: The heatmap has 7 columns, Mon–Sun in the local timezone.
- 07: The token endpoint returns clusters as ±0.5% bands ranked by USD.
- 08: Each signal fires at exactly its threshold and not just below it (spec). SPIKE never fires without covered history.

## Files / modules expected to change
`pyproject.toml`, `.gitignore`, `.env.example`, `liqdash/{config,parser,db,telegram_sync,binance,metrics,signals,api,cli}.py`, `liqdash/static/index.html`, `tests/` (+ `tests/fixtures/samples.jsonl`).

## Test scope
`uv run pytest tests/<file>` per changed module: parser → `test_parser.py`, db → `test_db.py`, telegram_sync → `test_sync.py`, binance → `test_binance.py`, metrics → `test_metrics.py`, api → `test_api_sync.py` (+ the heatmap/token specs from 06/07), signals → `test_signals.py`.
