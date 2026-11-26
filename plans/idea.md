# Binance Liquidation Dashboard: Design Document

**Status:** Idea / design stage (no code yet)
**Date:** 2026-11-25
**Timezone for all reports:** Asia/Saigon (UTC+7)

---

## 1. Goal

Build a personal dashboard that:

1. **Syncs on demand.** When I press **Sync**, it fetches every new message from the Telegram channel [t.me/BinanceLiquidations](https://t.me/BinanceLiquidations) since the last sync.
2. **Recaps liquidations** for each token, **daily** and **weekly**.
3. **Separates long and short** liquidations.
4. **Highlights tokens with large volume and large liquidations** so I can decide what to trade or watch.

---

## 2. Source Data

### 2.1 Message format

Sample messages:

```
🔴 #ETH Liquidated Long: $757K at $1642.96
🟢 #BTC Liquidated Short: $189K at $59244.00
```

| Part | Example | Meaning / notes |
|---|---|---|
| Emoji | 🔴 / 🟢 | 🔴 = long liquidated, 🟢 = short liquidated. Used only as a double-check |
| Token | `#ETH` | Base token only, with no `USDT` suffix and no exchange tag |
| Side | `Long` / `Short` | **Source of truth** for the side |
| Size | `$757K` | USD value, rounded to $1K. Suffix K / M / B |
| Price | `$1642.96` | Liquidation price, no thousands separators |
| Time | (message timestamp) | Taken from Telegram, converted to UTC+7 |

### 2.2 Parsing rules

- **Read every line on its own.** One Telegram message may contain several liquidation lines.
- **Convert sizes to plain dollars:** `$757K` → 757,000, `$1.2M` → 1,200,000, `$1.05B` → 1,050,000,000.
- **Keep token names exactly as written**, including names that start with digits (`#1000PEPE`, `#1000SATS`, `#1INCH`).
- **Store prices at full precision** (e.g. `$0.00001234`).
- **Skip and log lines that don't match** (ads, announcements). Never fail the whole sync because of one bad line.
- **Watch the skipped-line counter.** A sudden rise means the channel changed its format.

### 2.3 Known limitations of the data

- **Only large liquidations.** The channel likely has a minimum size, so small liquidations are missing. Check the smallest size seen over a few days and show it on the dashboard.
- **Binance only.** No other exchanges.
- **Undercounts during crashes.** Binance's own liquidation feed reports at most one liquidation per symbol per second, so totals will be lower than sites like Coinglass.
- **Rounding.** Sizes are rounded to $1K, which has a negligible effect on totals.

---

## 3. Telegram Setup (one-time, about 5 minutes)

1. Go to **my.telegram.org**, then **API development tools**, and create an app. Save the **api_id** and **api_hash**.
2. **Join** t.me/BinanceLiquidations in the Telegram app. "Unread" only exists for joined channels.
3. On the first sync, log in with your **phone number**, the **code** Telegram sends, and your **2FA password** if you have one.
4. The app saves a **session file**, so you won't need to log in again.

**Why not a bot?** A bot can only read channels whose admin added it. You don't own this channel, so the app reads it as your user account.

**Security**

- **Keep the session file private.** It works like a logged-in phone. Never upload it to GitHub or share it.
- **Keep api_id and api_hash private** for the same reason.
- The app only **reads** this one channel and, if you choose, marks it as read.
- To check or revoke access, go to Telegram **Settings → Devices**. The app appears there as a session.
- Avoid very aggressive history pulls to stay clear of rate limits. A first sync of a few weeks is safe.

---

## 4. Architecture

```
[Telegram channel] ──┐
                     ├──> Backend (Python) ──> Database (SQLite file) ──> Dashboard (browser)
[Binance public API]─┘         ▲                                              │
                               └────────────── "Sync" button ─────────────────┘
```

Everything runs **locally on my computer**. There's no server and no paid service.

### 4.1 Backend

- **Language:** Python
- **Telegram library:** Telethon (reads channels as a user account)
- **Web framework:** FastAPI (serves the dashboard and its data)

#### Sync flow (when Sync is pressed)

1. Read the **last synced message ID** from the database.
2. Fetch all **newer messages** from the channel. On the very first sync, go back a configurable number of days (e.g. 30).
3. **Split** each message into lines and **parse** each line.
4. **Save** new liquidations, using message ID + line number to skip duplicates.
5. Fetch **Binance Futures market data** for the tokens seen: 24h volume, open interest, price change and funding rate.
6. **Optionally** mark the messages as read in Telegram.
7. Return a summary, e.g. *"Synced 1,240 messages → 1,236 liquidations, 4 skipped lines."*

**Unread tracking:** The app keeps its **own last-synced message ID** instead of relying on Telegram's read marker. Then sync never misses or double-counts messages, even if I read the channel on my phone first.

#### Backend features (data the dashboard requests)

| Feature | Purpose |
|---|---|
| **Sync** | Run the sync flow and return the result |
| **Summary** | Per-token totals for a chosen day or week |
| **Token detail** | Timeline and price-level clusters for one token |
| **Status** | Last sync time, record count, skipped lines |

**Calculations are done on request** from the stored rows. No precomputed tables are needed, and formulas can change later without re-syncing.

#### Token → Binance market mapping

- Add `USDT` to the token (ETH → ETHUSDT, 1000PEPE → 1000PEPEUSDT).
- Keep a small **manual override list** for tokens that don't match.
- If no market is found, show **"no volume data"** instead of a wrong number.

### 4.2 Frontend dashboard

- **One HTML page** with a chart library (Chart.js or Apache ECharts), served by the backend.
- Open at `localhost:8000`.
- No build tools. React is an optional upgrade later (multiple pages, watchlists, alerts).

#### Layout

1. **Top bar:** Sync button with progress, last-sync time, **Day / Week** toggle, date picker
2. **Summary cards:** total long vs short liquidated, number of active tokens, biggest single liquidation
3. **Leaderboard table:** one row per token, sortable, with filters (minimum volume, minimum liquidation size)
4. **Long vs short bar chart:** top 15 tokens, longs to the left in red, shorts to the right in green
5. **Heatmap:** tokens × days (week view), colored by liquidation size
6. **Token detail panel:** opens on click, with a liquidation timeline and the price levels where liquidations clustered

### 4.3 Data storage

**One SQLite file** (`liquidations.db`) in the project folder. No install, no server, back up by copying the file.

| Table | Contents |
|---|---|
| **liquidations** | Message ID, line number, time, token, side, size (USD), price |
| **market_snapshots** | Per token, per sync: 24h volume, open interest, price, price change, funding rate |
| **sync_state** | Last synced message ID, last sync time |
| **skipped_lines** | Raw text of lines that didn't parse, with time |

**Other files**

- **`.env` settings:** api_id, api_hash, phone number, timezone, first-sync lookback days. *Private.*
- **Telegram session file:** login session. *Private.*

**Size estimate:** several thousand liquidations a day is only a few hundred MB per year. SQLite handles millions of rows easily.

**Example rows**

| Time (UTC+7) | Token | Side | Size (USD) | Price |
|---|---|---|---|---|
| … | ETH | Long | 757,000 | 1642.96 |
| … | BTC | Short | 189,000 | 59244.00 |

---

## 5. Metrics (per token, per day and per week)

| Metric | Why it matters |
|---|---|
| **Long liquidated ($)** | How much long positions got wiped out |
| **Short liquidated ($)** | How much short positions got squeezed |
| **Total liquidated ($) and count** | Overall activity |
| **Long/short ratio** | Which side is getting hurt |
| **Biggest single liquidation** | Sign of whales or very high leverage |
| **Price range of liquidations** | Where the pain levels are |
| **Change vs 7-day average** | Spots unusual spikes, not just tokens that are always big |
| **Liquidations ÷ 24h volume** | How violent the flush was relative to the token's size |
| **Open interest (and its change)** | How much leverage is left to be liquidated |
| **Price change and funding rate** | Context for which side is crowded |

Day boundaries use **UTC+7**. Weeks run Monday to Sunday.

**Key ranking:** tokens with **high volume and high liquidations as a share of volume**. This makes small and large coins comparable. $5M liquidated is normal for BTC but huge for a small altcoin.

---

## 6. Decision Signals (ideas to test, not trading rules)

| Signal | Possible meaning |
|---|---|
| Heavy **long** liquidations + price falling | Longs being flushed. Can mark capitulation or a local bottom, especially if open interest drops sharply |
| Heavy **short** liquidations + price rising | Short squeeze. Watch whether it continues or fades |
| **Spike vs 7-day average** | Something unusual is happening on that token |
| **One-sided** liquidations several days in a row | A trend punishing one side |
| **Clusters** at a price level | Levels where many traders had their liquidation price |

These can appear as **alert badges** next to each token in the leaderboard.

> This dashboard is a monitoring tool, not financial advice. Treat the signals as prompts to look closer.

---

## 7. Alternative Data Source

Instead of Telegram, connect directly to **Binance's public liquidation stream** (likely what the channel itself uses).

| | Telegram channel | Binance stream |
|---|---|---|
| Login needed | Yes (my Telegram account) | No |
| Size threshold | Yes (channel minimum) | No |
| History | Already in the channel, sync anytime | Only what I collect while it runs |
| Must run 24/7 | No | Yes |

**Decision for v1:** Telegram, because on-demand sync with existing history fits the "press Sync" workflow.

---

## 8. Future Options

- **Hosted version** for phone access: cheap VPS, PostgreSQL instead of SQLite, dashboard password, sync on a timer (e.g. every 15 minutes) plus the button.
- **Alerts:** notify (e.g. via my own Telegram bot) when a token crosses a spike or ratio threshold.
- **Watchlist:** pin tokens I'm trading.
- **Export:** CSV of daily/weekly recaps.

---

## 9. Open Questions

1. **Where should it run?** Local only, or hosted for phone access?
2. **Mark as read?** Should sync mark messages as read in Telegram?
3. **Priority:** daily "what happened" recap, or alerts when a token spikes?
4. **Format check:** collect 20–30 real messages (including a volatile day) to confirm there are no format variations.
5. **First-sync lookback:** how many days of history to pull initially?

---

## 10. Build Order (suggested)

1. Telegram setup and login (Section 3)
2. Parser, tested on real sample messages
3. Database and sync flow, with deduplication
4. Binance market data fetch
5. Summary calculations (daily / weekly per token)
6. Dashboard: leaderboard first, then charts, heatmap and token detail
7. Signals and alert badges