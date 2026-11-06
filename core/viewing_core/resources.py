"""Locate bundled files both from source and inside a PyInstaller build."""
import sys
from pathlib import Path


def resource(app_dir: Path, name: str) -> Path:
    """`app_dir` is the app package directory (pass Path(__file__).parent)."""
    base = Path(getattr(sys, "_MEIPASS", app_dir))
    return base / "resources" / name
