"""API endpoint tests using Flask test client."""
import json


def test_list_filters(client):
    r = client.get("/api/filters")
    assert r.status_code == 200
    data = r.get_json()
    assert "filters" in data
    names = [f["name"] for f in data["filters"]]
    assert "ema_crossover" in names
    assert "rsi_oversold" in names


def test_scan_dow(client):
    r = client.post(
        "/api/scan",
        data=json.dumps({
            "universe": "dow",
            "filters": [{"name": "above_ema", "params": {"period": 50}}],
            "interval": "1d",
            "period": "6mo",
        }),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "results" in data
    assert "total_scanned" in data
    assert "matched" in data
    assert isinstance(data["results"], list)


def test_scan_no_filters(client):
    r = client.post(
        "/api/scan",
        data=json.dumps({"universe": "dow", "filters": []}),
        content_type="application/json",
    )
    assert r.status_code == 200


def test_scan_invalid_universe(client):
    r = client.post(
        "/api/scan",
        data=json.dumps({"universe": "nyse", "filters": []}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_scan_unknown_filter(client):
    r = client.post(
        "/api/scan",
        data=json.dumps({
            "universe": "dow",
            "filters": [{"name": "nonexistent_filter_xyz", "params": {}}],
        }),
        content_type="application/json",
    )
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"TRADINGSCAN" in r.data or b"TradingScan" in r.data
