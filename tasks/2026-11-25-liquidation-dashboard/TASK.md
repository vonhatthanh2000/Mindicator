# 01 – Parser and local database
## Outcome
- Liquidation posts from the channel are read correctly into a local database, with long and short kept apart.
- Posts that aren't liquidations are set aside and counted, not lost or miscounted.
- Running it twice never counts the same liquidation twice.

# 02 – Telegram login and sync
## Outcome
- After a one-time login with my own Telegram account, one command pulls every new post since the last sync (the last 30 days on the first run).
- An interrupted sync picks up where it stopped, with no gaps or duplicates.
- My unread state in Telegram is left alone unless I choose otherwise.

# 03 – Binance market data
## Outcome
- Each crypto token has its trading volume, price move, open interest and funding rate from Binance.
- Stock and commodity tickers are recognised automatically and kept out of the recap.

# 04 – Daily and weekly recap numbers
## Outcome
- For any day or week (Vietnam time, weeks Monday to Sunday), every crypto token has long vs short totals, its biggest liquidation, its price range and how unusual the day is compared with recent days.
- Tokens are ranked by liquidations relative to their trading volume, so small and large coins can be compared.

# 05 – Dashboard: sync, cards and leaderboard
## Outcome
- A local web page with a Sync button that shows progress, headline totals, and a sortable, filterable leaderboard of tokens for the chosen day or week.

# 06 – Long/short chart and heatmap
## Outcome
- A chart shows at a glance which tokens had longs or shorts wiped out.
- A weekly heatmap shows which tokens were hit hardest on which days.

# 07 – Token detail panel
## Outcome
- Clicking a token shows when its liquidations happened and the price levels where they bunched up.

# 08 – Signal badges
## Outcome
- Tokens with unusual activity (spikes, long flushes, short squeezes, one-sided streaks, price clusters) are flagged with badges that explain why, as prompts to look closer, not trading advice.
