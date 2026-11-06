"""CSV Viewer - Professional lightweight offline CSV viewer for Windows 11."""
import sys
from pathlib import Path


def main():
    """Ultra-fast: Show window FIRST, load content SECOND (like PPTX)."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)
    app.setApplicationName("CSV Viewer")
    app.setApplicationVersion("1.0.0")

    # Show window IMMEDIATELY (no waiting for theme/files)
    from .ui.main_window import MainWindow
    window = MainWindow()
    window.show()  # FIRST - window appears instantly
    app.processEvents()  # Render window

    # Load theme in background
    def load_theme():
        from .ui.theme import sync_theme_to_windows
        sync_theme_to_windows(app)
        load_files()

    # Load files in background
    def load_files():
        for arg in sys.argv[1:]:
            if Path(arg).suffix.lower() == ".csv":
                window.open_file(str(Path(arg).absolute()))

    # Defer everything after window show (50ms = imperceptible to user)
    timer = QTimer()
    timer.timeout.connect(load_theme)
    timer.setSingleShot(True)
    timer.start(50)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
