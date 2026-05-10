"""
Busca de clientes via '@' no Command Palette.

Consulta a tabela clients + agrega últimos pedidos da tabela orders.
"""

from data.db import get_connection


def search_clients(query: str, limit: int = 20) -> list[dict]:
    """
    Busca clientes pelo nome (LIKE).
    Retorna lista de dicts com: id, name, whatsapp, order_count, last_order_title, last_order_status.
    """
    pattern = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.name,
                c.whatsapp,
                c.notes,
                COUNT(o.id)                          AS order_count,
                MAX(o.created_at)                    AS last_order_at,
                (SELECT title  FROM orders WHERE client_id = c.id
                 ORDER BY created_at DESC LIMIT 1)   AS last_order_title,
                (SELECT status FROM orders WHERE client_id = c.id
                 ORDER BY created_at DESC LIMIT 1)   AS last_order_status
            FROM   clients c
            LEFT JOIN orders o ON o.client_id = c.id
            WHERE  c.name LIKE ?
            GROUP  BY c.id
            ORDER  BY c.name
            LIMIT  ?
            """,
            (pattern, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def copy_whatsapp(client_id: int) -> str | None:
    """Retorna o WhatsApp do cliente para copiar para o clipboard."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT whatsapp FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
    return row["whatsapp"] if row and row["whatsapp"] else None
