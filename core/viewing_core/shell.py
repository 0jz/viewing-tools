"""Window behaviour shared by every viewer."""


class DropOpenMixin:
    """Mix into a QMainWindow: call setAcceptDrops(True), set `drop_suffixes`, define open_file(path)."""
    drop_suffixes: tuple = ()

    def _dropped_paths(self, e) -> list:
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        return [p for p in paths if not self.drop_suffixes or p.lower().endswith(self.drop_suffixes)]

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and self._dropped_paths(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for p in self._dropped_paths(e):
            self.open_file(p)
