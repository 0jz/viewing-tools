"""Run a callable on a QThread and report back through signals."""
from PySide6.QtCore import QObject, QThread, Signal


class _Worker(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:  # surfaced to the UI, not swallowed
            self.failed.emit(str(e))


def run_in_thread(fn, on_done, on_error, parent=None) -> QThread:
    """Execute fn() off the UI thread; on_done(result) / on_error(msg) run on the caller's thread.
    Keep a reference to the returned thread until it finishes."""
    thread = QThread(parent)
    worker = _Worker(fn)
    worker.moveToThread(thread)
    thread._worker = worker
    thread.started.connect(worker.run)
    worker.done.connect(on_done)
    worker.failed.connect(on_error)
    worker.done.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.start()
    return thread
