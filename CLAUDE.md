# TradingScan — Developer Guide

## Project Overview
Stock scanner web app. Browses NASDAQ + DOW JONES, filters stocks using technical criteria
translated from TradingView PineScript to Python.

## Setup

```bash
# 1. Create virtual env
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Configure API keys
cp env/.env.example env/.env
# Edit env/.env — set DATA_PROVIDER and any API keys

# 4. Install Playwright browsers
playwright install chromium

# 5. Run the app
flask --app src/app.py run
```

## Running Tests

```bash
# Unit + API tests (no network, uses mock provider)
pytest tests/ --ignore=tests/e2e -v

# E2E tests (starts real Flask server)
pytest tests/e2e -v
```

## Adding a New PineScript Filter

1. Create `src/filters/pinescript_converted/my_filter.py`
2. Subclass `BaseFilter`, set `name`, `description`, `params`
3. Implement `apply(df) -> bool`
4. The filter is auto-discovered on startup — no registry edit needed

See `src/filters/pinescript_converted/README.md` for the full template and
PineScript → Python cheat sheet.

## Data Providers

Set `DATA_PROVIDER` in `env/.env`:
- `yfinance` — free, no key, good for development
- `alphavantage` — requires `ALPHA_VANTAGE_API_KEY`
- `polygon` — requires `POLYGON_API_KEY`, best for production
- `mock` — synthetic data, used automatically in tests

## Project Structure

```
src/
  config.py            # Loads env/.env
  app.py               # Flask factory
  data/                # Providers, fetcher, universe, cache
  indicators/          # EMA, SMA, RSI, MACD, BBands, ATR, VWAP
  filters/             # Built-in filters + pinescript_converted/
  scanner/             # Engine, pipeline, result dataclass
  api/                 # REST: /api/scan, /api/filters
  views/               # Page routes
  templates/           # Jinja2 HTML
  static/              # CSS, JS
tests/
  conftest.py          # Fixtures (mock provider)
  test_indicators.py
  test_filters.py
  test_api.py
  e2e/                 # Playwright tests
env/
  .env                 # Real keys (gitignored)
  .env.example         # Template (committed)
```
