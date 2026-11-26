import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DB = "liquidations.db"

# Token -> Binance symbol, for tokens where token + "USDT" is wrong.
SYMBOL_OVERRIDES: dict[str, str] = {}


def _get(key, default):
    v = os.getenv(key)
    return default if v is None or v == "" else v


@dataclass(frozen=True)
class Settings:
    TG_API_ID: str | None = _get("TG_API_ID", None)
    TG_API_HASH: str | None = _get("TG_API_HASH", None)
    TG_PHONE: str | None = _get("TG_PHONE", None)
    TIMEZONE: str = _get("TIMEZONE", "Asia/Saigon")
    LOOKBACK_DAYS: int = int(_get("LOOKBACK_DAYS", 30))
    MARK_AS_READ: bool = _get("MARK_AS_READ", "false").lower() == "true"
    LIQ_DB: str = _get("LIQ_DB", DEFAULT_DB)
    SPIKE_MULT: float = float(_get("SPIKE_MULT", 3))
    SPIKE_MIN_USD: float = float(_get("SPIKE_MIN_USD", 500_000))
    SIDE_SHARE: float = float(_get("SIDE_SHARE", 0.7))
    FLUSH_MIN_USD: float = float(_get("FLUSH_MIN_USD", 1_000_000))
    STREAK_DAYS: int = int(_get("STREAK_DAYS", 3))
    CLUSTER_BAND_PCT: float = float(_get("CLUSTER_BAND_PCT", 0.005))
    CLUSTER_MIN_COUNT: int = int(_get("CLUSTER_MIN_COUNT", 5))
    CLUSTER_MIN_SHARE: float = float(_get("CLUSTER_MIN_SHARE", 0.3))
    CLUSTER_MIN_USD: float = float(_get("CLUSTER_MIN_USD", 500_000))

    def require(self, *keys):
        """Return the values of keys that have no default; raise naming the first missing one.

        Call it only from the commands that need the keys, so offline commands work without them.
        """
        values = []
        for key in keys:
            value = getattr(self, key)
            if value is None:
                raise ConfigError(f"Missing required setting {key} in .env")
            values.append(value)
        return values


class ConfigError(Exception):
    pass


settings = Settings()
