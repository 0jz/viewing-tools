from PySide6.QtCore import QSettings

from viewing_core import RecentFiles


def test_recent_files_order_limit_and_forget(tmp_path):
    s = QSettings(str(tmp_path / "t.ini"), QSettings.IniFormat)
    r = RecentFiles(s, limit=3)
    for name in "abcd":
        r.push(name)
    assert r.get() == ["d", "c", "b"]
    r.push("b")
    assert r.get() == ["b", "d", "c"]
    r.forget("d")
    assert r.get() == ["b", "c"]
    r.clear()
    assert r.get() == []
