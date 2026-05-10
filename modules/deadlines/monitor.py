from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from modules.deadlines.scanner import get_classified_orders


class DeadlineMonitor(QObject):
    """
    Scans orders every 30 minutes and emits signals when status changes.
    Runs in the main thread (QTimer) — DB reads are fast enough.
    """

    status_changed   = pyqtSignal(str)          # 'ok' | 'warning' | 'critical'
    alert_triggered  = pyqtSignal(str, str, bool)  # title, message, is_critical

    _INTERVAL_MS = 30 * 60 * 1_000   # 30 min

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_status = "ok"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.scan)
        self._timer.start(self._INTERVAL_MS)

    def scan(self) -> str:
        """Perform an immediate scan and return the overall status."""
        orders = get_classified_orders()

        has_critical = any(o["deadline_status"] == "critical" for o in orders)
        has_warning  = any(o["deadline_status"] == "warning"  for o in orders)

        if has_critical:
            new_status = "critical"
            critical = [o for o in orders if o["deadline_status"] == "critical"]
            names = ", ".join(o["title"] for o in critical[:3])
            if len(critical) > 3:
                names += f" (+{len(critical) - 3})"
            self.alert_triggered.emit("Prazos Críticos", names, True)
        elif has_warning:
            new_status = "warning"
        else:
            new_status = "ok"

        if new_status != self._last_status:
            self._last_status = new_status
            self.status_changed.emit(new_status)

        return new_status
