import logging

import pytest

from liqdash.parser import parse_message


def one(text):
    rows, skipped = parse_message(1, 100, text)
    assert skipped == [] and len(rows) == 1
    return rows[0]


@pytest.mark.parametrize(
    "size,expected",
    [("$757K", 757_000), ("$90.8K", 90_800), ("$1.2M", 1_200_000), ("$1.05B", 1_050_000_000), ("$500", 500)],
)
def test_sizes(size, expected):
    assert one(f"🔴 #ETH Liquidated Long: {size} at $1642.96")[5] == expected


@pytest.mark.parametrize("token", ["1000PEPE", "1000SATS", "1INCH", "币安人生"])
def test_tokens_kept_as_written(token):
    assert one(f"🟢 #{token} Liquidated Short: $75K at $0.2512")[3] == token


def test_price_kept_as_exact_text():
    assert one("🔴 #1000PEPE Liquidated Long: $1.2M at $0.00001234")[6] == "0.00001234"
    assert one("🔴 #BTC Liquidated Long: $100K at $59032.00")[6] == "59032.00"


def test_row_shape():
    assert one("🔴 #ETH Liquidated Long: $757K at $1642.96") == (1, 0, 100, "ETH", "Long", 757_000, "1642.96")


def test_multi_line_numbering_ignores_empty_lines():
    text = "🔴 #ETH Liquidated Long: $757K at $1642.96\n\n  \n🟢 #BTC Liquidated Short: $189K at $59244.00"
    rows, skipped = parse_message(7, 100, text)
    assert [(r[1], r[3], r[4]) for r in rows] == [(0, "ETH", "Long"), (1, "BTC", "Short")]
    assert skipped == []


@pytest.mark.parametrize("text", [None, "", "\n\n"])
def test_message_without_text_yields_nothing(text):
    assert parse_message(1, 100, text) == ([], [])


def test_non_matching_line_is_skipped_not_fatal():
    text = "📢 Join our premium group!\n🔴 #ETH Liquidated Long: $757K at $1642.96"
    rows, skipped = parse_message(5, 100, text)
    assert skipped == [(5, 0, 100, "📢 Join our premium group!")]
    assert rows[0][1] == 1


@pytest.mark.parametrize(
    "line",
    [
        "🔴 #ETH Liquidated Long: $1,757K at $1642.96",  # comma in size
        "🔴 #ETH Liquidated Long: $757K at $1,642.96",  # comma in price
        "🔴 #ETH Liquidated Sideways: $757K at $1642.96",
        "🔴 #ETH Liquidated Long: $757K at $1642.96 extra",
    ],
)
def test_format_variants_are_skipped(line):
    rows, skipped = parse_message(1, 100, line)
    assert rows == [] and len(skipped) == 1


def test_emoji_mismatch_keeps_side_word_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        row = one("🟢 #ETH Liquidated Long: $757K at $1642.96")
    assert row[4] == "Long"
    assert "mismatch" in caplog.text


def test_missing_emoji_and_trailing_spaces():
    assert one("   #ETH Liquidated Short: $10K at $1.5   ")[3:6] == ("ETH", "Short", 10_000)
