# Pivotal choices: Binance Liquidation Dashboard

## 1. Read the channel with Telethon as my own account
**Chosen:** the Telegram user API (Telethon) logged in as my account, over the no-login public web page `t.me/s/BinanceLiquidations` (or supporting both).
**Status:** confirmed by user, 2026-11-25.

**Main function**
This is how every liquidation gets into the app. Sync asks Telegram for every post after the last message ID the app saved.

**Effect on the project**
Login, the session file and the private `.env` keys exist only because of this choice. Sync depends on Telegram's paging by message ID, which is reliable and handles large pulls. It also allows the optional mark-as-read. Switching to the web page later would mean rewriting only the fetch part; the parser and database stay the same.

**Trade-offs**
We gain an official, stable API and quick large syncs (30 days, about 17K posts). We give up a no-setup start: a one-time phone, code and 2FA login, plus a session file that must stay private, because it works like a logged-in phone.

**Scenarios**
- Normal: I press Sync after a day away, and about 600 new posts arrive in a few seconds.
- Load / edge: the first sync pulls 30 days. Telegram may ask us to wait (flood wait); Telethon sleeps and continues, so the sync is just slower.
- Failure: the session gets revoked (Settings → Devices). Sync stops with "Not logged in: run 'uv run liq-login' first". Data already saved is kept, and the next sync resumes from the last saved message.

## 2. Volume and price for past days come from hourly Binance candles
**Chosen:** hourly candles added up into Vietnam-time days and weeks, over a snapshot taken at sync time (which gives past days today's numbers) and over daily candles (which cut days at UTC midnight, i.e. 07:00 Vietnam time).
**Status:** confirmed by user, 2026-11-25 (first as daily candles, then as hourly candles for correct UTC+7 day edges).

**Main function**
It provides the volume and price move behind the key ranking, "liquidations as a share of volume", for whichever day or week is selected.

**Effect on the project**
It adds an hourly candle table and an incremental fetch to every sync. Open interest uses Binance's hourly history, which only goes back about 30 days (requests are clamped to 29). Only finished hours are stored, so the current hour is never frozen half-built. Funding rate is a current value only.

**Trade-offs**
We gain exact numbers for any past day in local time. The cost is more Binance requests (about one per token per sync, more on the first sync) and a larger table (roughly 24 rows per token per day, still small).

**Scenarios**
- Normal: I look at last Tuesday. The ETH ratio uses the volume traded between 00:00 and 24:00 Vietnam time that Tuesday.
- Load / edge: I look at a day more than 30 days back. Volume and price still work, but open interest shows as missing.
- Failure: Binance rate-limits or is unreachable. The Telegram part of the sync still succeeds, the summary reports which tokens weren't updated, and those cells show "no volume data" until the next sync.
