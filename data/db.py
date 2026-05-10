import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "grafica.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                whatsapp    TEXT,
                notes       TEXT,
                created_at  REAL    DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                os_number       TEXT,
                client_id       INTEGER REFERENCES clients(id),
                title           TEXT    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'Entrada',
                deadline        REAL,
                value           REAL,
                notes           TEXT,
                todoist_task_id TEXT,
                last_moved_at   REAL    DEFAULT (unixepoch()),
                created_at      REAL    DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                text        TEXT    NOT NULL,
                trigger_at  REAL    NOT NULL,
                recurrence  TEXT,
                dismissed   INTEGER DEFAULT 0,
                created_at  REAL    DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS file_index (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT    NOT NULL,
                filepath    TEXT    NOT NULL UNIQUE,
                folder      TEXT    NOT NULL,
                extension   TEXT,
                size        INTEGER,
                modified_at REAL,
                indexed_at  REAL    DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_file_filename  ON file_index(filename);
            CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_reminders_at   ON reminders(trigger_at);
        """)
