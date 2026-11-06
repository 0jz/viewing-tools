"""Shared shell for the Viewing Tools apps: theme, settings, drag-drop, resources, workers."""
from .resources import resource
from .settings import RecentFiles
from .shell import DropOpenMixin
from .theme import apply_theme
from .worker import run_in_thread

__all__ = ["resource", "RecentFiles", "DropOpenMixin", "apply_theme", "run_in_thread"]
