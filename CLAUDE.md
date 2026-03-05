# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Commands

**Run the app:**
```bash
cd src
python app.py
```
App runs at http://127.0.0.1:5000

**Run tests:**
```bash
python -m unittest discover -s tests
```

**Run a single test:**
```bash
python -m unittest tests.test_app.AppTestCase.test_index
```

**Production:**
```bash
gunicorn src.app:app
```

## Architecture

Flask MVC app — all source code lives in `src/`:

- **`app.py`**: Flask app factory; registers two URL rules (`/` and `/course/<course_id>`)
- **`models.py`**: `Course` dataclass with in-memory sample data (3 hardcoded courses indexed 1–3)
- **`views.py`**: Route handlers `index()` and `course(course_id)` that render templates
- **`templates/`**: Jinja2 templates; `layout.html` is the base that others extend
- **`static/css/styles.css`**: All styling

The app has no database — course data is defined directly in `models.py`. Adding a real data source means updating the `Course` class and the sample data there, then updating `views.py` to query it.

Tests use Python's built-in `unittest` with Flask's test client (`app.test_client()`). Import `app` from `src/app.py` when writing tests.
