import json
import time
from pathlib import Path

from data.db import get_connection

SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "settings.json"

_TERMINAL_STATUSES = {"Pronto", "Entregue"}


def _thresholds() -> dict[str, float]:
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return settings.get("kanban", {}).get("alert_thresholds_hours", {})
    except Exception:
        return {}


def get_stale_orders() -> list[dict]:
    """
    Returns orders that have been in the same column longer than the configured
    threshold (hours).  Terminal statuses (Pronto / Entregue) are excluded.
    """
    thresholds = _thresholds()
    if not thresholds:
        return []

    now = time.time()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.id, o.title, o.status, o.last_moved_at,
                   c.name AS client_name
            FROM   orders o
            LEFT JOIN clients c ON c.id = o.client_id
            WHERE  o.status NOT IN ('Pronto', 'Entregue')
            """
        ).fetchall()

    stale = []
    for row in rows:
        d = dict(row)
        threshold_h = thresholds.get(d["status"])
        if threshold_h is None:
            continue
        hours_stuck = (now - (d["last_moved_at"] or now)) / 3600
        if hours_stuck >= threshold_h:
            d["hours_stuck"] = round(hours_stuck, 1)
            stale.append(d)

    return stale
