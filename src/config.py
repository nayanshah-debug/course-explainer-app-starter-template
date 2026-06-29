import os
from pathlib import Path
from dotenv import load_dotenv

# Load from env/.env relative to project root
_env_path = Path(__file__).resolve().parent.parent / "env" / ".env"
load_dotenv(_env_path)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    # Data provider
    DATA_PROVIDER = os.getenv("DATA_PROVIDER", "yfinance")
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

    # Schwab
    SCHWAB_API_KEY      = os.getenv("SCHWAB_API_KEY", "")
    SCHWAB_API_SECRET   = os.getenv("SCHWAB_API_SECRET", "")
    # If multiple callback URLs are registered (comma-separated), use the first one
    SCHWAB_CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1").split(",")[0].strip()
    SCHWAB_TOKEN_PATH   = os.getenv("SCHWAB_TOKEN_PATH") or str(
        Path(__file__).resolve().parent.parent / "env" / "schwab_token.json"
    )

    # Robinhood
    RH_USERNAME = os.getenv("ROBINHOOD_USERNAME", "")
    RH_PASSWORD = os.getenv("ROBINHOOD_PASSWORD", "")

    # Cache
    REDIS_URL = os.getenv("REDIS_URL", "")
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    # Scanner
    SCAN_CONCURRENCY = int(os.getenv("SCAN_CONCURRENCY", "10"))
