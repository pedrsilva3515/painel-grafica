import json
import time
from pathlib import Path

from data.db import get_connection

SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "settings.json"


def get_columns() -> list[str]:
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return settings.get("kanban", {}).get("columns", _DEFAULT_COLUMNS)
    except Exception:
        return _DEFAULT_COLUMNS


_DEFAULT_COLUMNS = [
    "Entrada", "Arte Final", "Aguardando Aprovação",
    "Produção", "Acabamento", "Pronto", "Entregue",
]


def get_orders_by_column() -> dict[str, list[dict]]:
    columns = get_columns()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.id, o.os_number, o.title, o.status,
                   o.deadline, o.value, o.notes,
                   o.last_moved_at, o.created_at,
                   c.name AS client_name
            FROM   orders o
            LEFT JOIN clients c ON c.id = o.client_id
            ORDER  BY o.created_at DESC
            """
        ).fetchall()

    result: dict[str, list[dict]] = {col: [] for col in columns}
    for row in rows:
        d = dict(row)
        if d["status"] in result:
            result[d["status"]].append(d)
    return result


def add_order(
    title: str,
    os_number: str = "",
    client_name: str = "",
    deadline: float | None = None,
    value: float | None = None,
    notes: str = "",
    created_at: float | None = None,
) -> int:
    with get_connection() as conn:
        client_id = None
        if client_name.strip():
            row = conn.execute(
                "SELECT id FROM clients WHERE name = ?", (client_name.strip(),)
            ).fetchone()
            if row:
                client_id = row["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO clients (name) VALUES (?)", (client_name.strip(),)
                )
                client_id = cur.lastrowid

        cur = conn.execute(
            """
            INSERT INTO orders (os_number, client_id, title, deadline, value, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (os_number, client_id, title, deadline, value, notes),
        )
        order_id = cur.lastrowid

        if created_at is not None:
            conn.execute(
                "UPDATE orders SET created_at = ?, last_moved_at = ? WHERE id = ?",
                (created_at, created_at, order_id),
            )
        return order_id


def update_order(order_id: int, **kwargs) -> None:
    allowed = {"title", "os_number", "deadline", "value", "notes", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    parts = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE orders SET {parts} WHERE id = ?",
            (*updates.values(), order_id),
        )


def move_order(order_id: int, new_status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = ?, last_moved_at = ? WHERE id = ?",
            (new_status, time.time(), order_id),
        )


def delete_order(order_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
