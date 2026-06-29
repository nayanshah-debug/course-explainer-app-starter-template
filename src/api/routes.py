import threading
import uuid
from flask import Blueprint, jsonify, request
from src.filters import FILTER_REGISTRY
from src.scanner.pipeline import build_filters, run_scan

bp = Blueprint("api", __name__)

# In-memory job store: job_id → job dict
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _make_job():
    return {
        "status":    "running",   # running | done | error
        "completed": 0,
        "total":     0,
        "matched":   0,
        "results":   [],
        "error":     None,
    }


def _run_job(job_id: str, universe: str, filter_specs: list, interval: str, period: str, symbols: list):
    """Background thread: runs the scan and updates the job dict as progress arrives."""
    def on_progress(completed, total, result):
        with _jobs_lock:
            job = _jobs[job_id]
            job["completed"] = completed
            job["total"]     = total
            if result is not None:
                job["matched"] += 1
                job["results"].append(result.to_dict())

    try:
        from src.scanner.pipeline import run_scan as _run
        _run(universe, filter_specs, interval, period, symbols=symbols, progress_callback=on_progress)
        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"]  = str(exc)


@bp.get("/filters")
def list_filters():
    """Return all available filters and their param schemas."""
    filters = [
        {"name": name, "description": cls.description, "params": cls.params}
        for name, cls in FILTER_REGISTRY.items()
    ]
    return jsonify({"filters": filters})


@bp.post("/scan")
def scan():
    """
    Start an async scan. Returns job_id immediately.
    Poll GET /api/scan/<job_id> for progress and results.

    Body: { universe, filters, interval, period, symbols? }
    """
    body = request.get_json(force=True) or {}
    universe     = body.get("universe", "dow")
    filter_specs = body.get("filters", [])
    interval     = body.get("interval", "1d")
    period       = body.get("period", "6mo")
    symbols      = body.get("symbols", [])

    if symbols:
        universe = "symbols"

    if universe not in ("nasdaq", "nyse", "nasdaq_nyse", "dow", "both", "all_us", "symbols"):
        return jsonify({"error": "invalid universe"}), 400
    if universe == "symbols" and not symbols:
        return jsonify({"error": "symbols list required"}), 400
    if not isinstance(filter_specs, list):
        return jsonify({"error": "filters must be a list"}), 400

    try:
        build_filters(filter_specs)   # validate filter names & params before starting
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = _make_job()

    t = threading.Thread(
        target=_run_job,
        args=(job_id, universe, filter_specs, interval, period, symbols),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id})


@bp.get("/scan/<job_id>")
def scan_status(job_id: str):
    """Poll this endpoint for live progress and results."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)
