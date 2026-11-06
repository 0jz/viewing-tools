"""Recent-files list persisted in QSettings."""
from pathlib import Path

from PySide6.QtCore import QSettings


class RecentFiles:
    def __init__(self, settings: QSettings, key: str = "recent", limit: int = 10):
        self.settings, self.key, self.limit = settings, key, limit

    def get(self) -> list:
        v = self.settings.value(self.key, [])
        if isinstance(v, str):
            v = [v] if v else []
        return [x for x in v] if isinstance(v, list) else []

    def existing(self) -> list:
        return [x for x in self.get() if Path(x).exists()]

    def push(self, path: str) -> None:
        rest = [x for x in self.get() if x != path]
        self.settings.setValue(self.key, ([path] + rest)[:self.limit])

    def forget(self, path: str) -> None:
        self.settings.setValue(self.key, [x for x in self.get() if x != path])

    def clear(self) -> None:
        self.settings.setValue(self.key, [])
