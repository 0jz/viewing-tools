"""Light/dark palettes; mode is "system" (follow Windows), "light" or "dark"."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _palette(dark: bool) -> QPalette:
    p = QPalette()
    if dark:
        c = dict(Window=(37, 38, 43), WindowText=(232, 234, 241), Base=(28, 29, 34), AlternateBase=(37, 38, 43),
                 Text=(232, 234, 241), Button=(48, 50, 58), ButtonText=(232, 234, 241), ToolTipBase=(60, 62, 70),
                 ToolTipText=(232, 234, 241), Highlight=(76, 110, 245), HighlightedText=(255, 255, 255),
                 Link=(116, 143, 252), PlaceholderText=(139, 147, 168))
    else:
        c = dict(Window=(244, 245, 247), WindowText=(28, 32, 48), Base=(255, 255, 255), AlternateBase=(240, 241, 244),
                 Text=(28, 32, 48), Button=(255, 255, 255), ButtonText=(28, 32, 48), ToolTipBase=(255, 255, 225),
                 ToolTipText=(0, 0, 0), Highlight=(59, 91, 219), HighlightedText=(255, 255, 255),
                 Link=(59, 91, 219), PlaceholderText=(106, 113, 132))
    for name, rgb in c.items():
        p.setColor(getattr(QPalette, name), QColor(*rgb))
    return p


def apply_theme(app: QApplication, mode: str = "system") -> bool:
    """Apply the palette for `mode` and return True if it is dark."""
    if mode == "system":
        try:
            dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            dark = False
    else:
        dark = mode == "dark"
    app.setPalette(_palette(dark))
    return dark
