"""CSV Viewer theme: delegates to the shared core palette."""
from viewing_core import apply_theme


def sync_theme_to_windows(app):
    apply_theme(app, "system")
