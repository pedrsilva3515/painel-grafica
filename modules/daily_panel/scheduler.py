import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "settings.json"


def _panel_time() -> tuple[int, int]:
    try:
        s = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        h, m = s.get("daily_panel", {}).get("time", "08:00").split(":")
        return int(h), int(m)
    except Exception:
        return 8, 0


class DailyPanelScheduler(QObject):
    """
    Checks the clock every minute.  Fires `trigger` once per day at the
    configured time (default 08:00).
    """

    trigger = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fired_on: str | None = None   # date string of last fire

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)
        self._timer.start(60_000)   # every 60 s

    def _check(self):
        now    = datetime.now()
        today  = now.strftime("%Y-%m-%d")
        target_h, target_m = _panel_time()

        if self._fired_on == today:
            return

        if now.hour == target_h and now.minute >= target_m:
            self._fired_on = today
            self.trigger.emit()
