import time

from data.db import get_connection


def classify(deadline_ts: float | None) -> str:
    """Return 'critical', 'warning', or 'ok' for a deadline timestamp."""
    if deadline_ts is None:
        return "ok"
    diff_h = (deadline_ts - time.time()) / 3600
    if diff_h < 24:
        return "critical"
    if diff_h < 48:
        return "warning"
    return "ok"


def get_classified_orders() -> list[dict]:
    """
    All non-delivered orders that have a deadline, sorted nearest-first.
    Each dict gets an extra 'deadline_status' key.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.id, o.os_number, o.title, o.status, o.deadline,
                   c.name AS client_name
            FROM   orders o
            LEFT JOIN clients c ON c.id = o.client_id
            WHERE  o.deadline IS NOT NULL
              AND  o.status   != 'Entregue'
            ORDER  BY o.deadline ASC
            """
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["deadline_status"] = classify(d["deadline"])
        result.append(d)
    return result
