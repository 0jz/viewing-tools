"""PPTX Viewer - fast, offline PowerPoint viewer for Windows (PySide6 / Qt6)."""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from viewing_core import apply_theme, resource as _resource
from .ui import MainWindow


def resource(name: str) -> Path:
    return _resource(Path(__file__).parent, name)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PPTX Viewer")
    app.setOrganizationName("PptxViewer")
    app.setStyle("Fusion")
    ico = resource("app.ico")
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    mode = QSettings("PptxViewer", "PptxViewer").value("theme", "system")
    dark = apply_theme(app, mode)
    win = MainWindow()
    win.canvas.dark = dark
    app.styleHints().colorSchemeChanged.connect(
        lambda *_: win.theme_mode == "system" and setattr(win.canvas, "dark", apply_theme(app, "system")))
    win.show()

    for arg in sys.argv[1:]:
        if arg.lower().endswith(".pptx"):
            win.open_file(str(Path(arg).absolute()))
            break
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
