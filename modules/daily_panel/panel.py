import time

from data.db import get_connection
from modules.deadlines.scanner import get_classified_orders
from modules.kanban.alerts import get_stale_orders


def get_daily_summary() -> dict:
    """
    Aggregate all data needed for the morning briefing panel.
    Returns a dict with keys: critical, warning, due_today, stale, reminders.
    """
    orders = get_classified_orders()

    now        = time.time()
    day_start  = now - (now % 86_400)          # midnight UTC (approx)
    day_end    = day_start + 86_400

    critical  = [o for o in orders if o["deadline_status"] == "critical"]
    warning   = [o for o in orders if o["deadline_status"] == "warning"]
    due_today = [
        o for o in orders
        if o.get("deadline") and day_start <= o["deadline"] <= day_end
    ]

    stale = get_stale_orders()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT text, trigger_at FROM reminders
            WHERE  dismissed   = 0
              AND  trigger_at BETWEEN ? AND ?
            ORDER  BY trigger_at ASC
            """,
            (day_start, day_end),
        ).fetchall()
    reminders = [dict(r) for r in rows]

    return {
        "critical":  critical,
        "warning":   warning,
        "due_today": due_today,
        "stale":     stale,
        "reminders": reminders,
    }
