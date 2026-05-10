from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QTabWidget

from ui.kanban_widget import KanbanWidget
from ui.deadlines_widget import DeadlinesWidget


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Painel Gráfica")
        self.setMinimumSize(1_100, 680)
        self._build_ui()

    def _build_ui(self):
        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        tabs.addTab(KanbanWidget(), "📋  Kanban")
        tabs.addTab(DeadlinesWidget(), "⏰  Prazos")
        self.setCentralWidget(tabs)

    def show_kanban_tab(self):
        self.centralWidget().setCurrentIndex(0)
        self.show()
        self.raise_()
        self.activateWindow()

    def show_deadlines_tab(self):
        self.centralWidget().setCurrentIndex(1)
        self.show()
        self.raise_()
        self.activateWindow()
