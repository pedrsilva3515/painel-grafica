"""
Gerenciador de lembretes.

- Persiste lembretes no SQLite (tabela reminders).
- QTimer verifica a cada 60s se algum lembrete deve disparar.
- Emite sinal reminder_triggered(text) para o tray exibir notificação.
- Parser de linguagem natural para "!texto 14h", "!texto amanhã 9h30".
"""

import re
import time
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from data.db import get_connection


# ── Parser de horário ─────────────────────────────────────────────────────────

def parse_reminder(raw: str) -> tuple[str, float] | None:
    """
    Recebe texto sem o '!' inicial.
    Retorna (texto_do_lembrete, timestamp_unix) ou None se não parsear.

    Formatos suportados:
      "ligar fornecedor 14h"
      "ligar fornecedor 14:30"
      "ligar fornecedor amanhã 9h"
      "ligar fornecedor amanhã 9:30"
      "reunião em 30min"
      "reunião em 2h"
    """
    raw = raw.strip()
    now = datetime.now()

    # "em Xmin" ou "em Xh"
    m = re.search(r"\bem\s+(\d+)\s*(min(?:utos?)?|h(?:oras?)?)\b", raw, re.I)
    if m:
        qty = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(minutes=qty) if unit.startswith("min") else timedelta(hours=qty)
        trigger = now + delta
        text = re.sub(r"\bem\s+\d+\s*(?:min(?:utos?)?|h(?:oras?)?)\b", "", raw, flags=re.I).strip()
        return (text or raw, trigger.timestamp())

    # "amanhã HHh" ou "amanhã HH:MM"
    base_date = now.date()
    prefix = ""
    m_amanha = re.search(r"\bamanh[ãa]\b", raw, re.I)
    if m_amanha:
        base_date = (now + timedelta(days=1)).date()
        prefix = m_amanha.group(0)

    # Hora no formato "14h", "14h30", "14:30", "9h", "9:30"
    m_time = re.search(r"\b(\d{1,2})(?:[h:](\d{2})?)?\s*h?\b", raw, re.I)
    if m_time:
        hour = int(m_time.group(1))
        minute = int(m_time.group(2)) if m_time.group(2) else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            trigger_dt = datetime(base_date.year, base_date.month, base_date.day, hour, minute)
            # Se o horário já passou hoje, agenda para amanhã
            if trigger_dt <= now and not m_amanha:
                trigger_dt += timedelta(days=1)
            # Remove partes de hora e "amanhã" do texto
            text = re.sub(r"\bamanh[ãa]\b", "", raw, flags=re.I)
            text = re.sub(r"\b\d{1,2}(?:[h:]\d{0,2})?\s*h?\b", "", text, flags=re.I).strip()
            text = text.strip(" -–")
            return (text or raw, trigger_dt.timestamp())

    return None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def add_reminder(text: str, trigger_at: float, recurrence: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (text, trigger_at, recurrence) VALUES (?, ?, ?)",
            (text, trigger_at, recurrence),
        )
        return cur.lastrowid


def get_pending() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE dismissed = 0 ORDER BY trigger_at",
        ).fetchall()
    return [dict(r) for r in rows]


def dismiss(reminder_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE reminders SET dismissed = 1 WHERE id = ?", (reminder_id,))


# ── Manager ───────────────────────────────────────────────────────────────────

class ReminderManager(QObject):
    """
    Objeto de longa duração (criado em main.py).
    Verifica lembretes a cada 60s e emite reminder_triggered quando dispara.
    """

    reminder_triggered = pyqtSignal(str, str)   # title, body

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    def _check(self):
        now = time.time()
        for r in get_pending():
            if r["trigger_at"] <= now:
                dismiss(r["id"])
                self.reminder_triggered.emit("⏰ Lembrete", r["text"])

                # Reagendar se recorrente
                if r.get("recurrence") == "daily":
                    add_reminder(r["text"], r["trigger_at"] + 86_400, "daily")
                elif r.get("recurrence") == "weekly":
                    add_reminder(r["text"], r["trigger_at"] + 7 * 86_400, "weekly")
