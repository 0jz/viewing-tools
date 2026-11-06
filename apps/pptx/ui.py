"""Main window, slide canvas and presentation mode."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSettings, QSize, QSizeF, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QGuiApplication, QIcon, QKeySequence, QPageSize, QPainter,
                           QPalette, QPdfWriter, QPixmap)
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QLabel, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QStackedWidget, QToolBar, QVBoxLayout, QWidget)

from viewing_core import DropOpenMixin, apply_theme
from .parser import Deck, PptxError
from .render import paint_background, paint_slide, render_pixmap

APP_NAME = "PPTX Viewer"
THUMB_W = 168
MARGIN = 24
ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]


# --------------------------------------------------------------------------- canvas
class SlideCanvas(QWidget):
    """Paints one slide, centred, at the current zoom."""

    def __init__(self, scroll: QScrollArea):
        super().__init__()
        self.scroll = scroll
        self.deck: Deck | None = None
        self.index = 0
        self.zoom: float | None = None  # None = fit
        self.scale = 1.0
        self.cache: dict = {}
        self.dark = False
        scroll.viewport().installEventFilter(self)
        self.setAutoFillBackground(False)

    def set_deck(self, deck, index=0):
        self.deck, self.index, self.cache = deck, index, {}
        self.relayout()

    def set_index(self, i):
        self.index = i
        self.update()

    def eventFilter(self, obj, ev):
        if obj is self.scroll.viewport() and ev.type() == QEvent.Resize:
            self.relayout()
        return False

    def relayout(self):
        vp = self.scroll.viewport().size()
        if self.deck is None:
            self.resize(vp)
            return
        W, H = self.deck.width, self.deck.height
        fit = min((vp.width() - 2 * MARGIN) / W, (vp.height() - 2 * MARGIN) / H)
        self.scale = max(0.05, fit if self.zoom is None else self.zoom)
        self.resize(max(vp.width(), int(W * self.scale + 2 * MARGIN)), max(vp.height(), int(H * self.scale + 2 * MARGIN)))
        self.update()

    def slide_rect(self) -> QRectF:
        w, h = self.deck.width * self.scale, self.deck.height * self.scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(20, 21, 25) if self.dark else QColor(222, 225, 232))
        if self.deck is None:
            return
        r = self.slide_rect()
        p.fillRect(r.translated(0, 3).adjusted(-1, 0, 1, 1), QColor(0, 0, 0, 60))
        p.save()
        p.setClipRect(r)
        p.translate(r.topLeft())
        p.scale(self.scale, self.scale)
        try:
            s = self.deck.slide(self.index)
            paint_background(p, s, self.deck.width, self.deck.height)
            paint_slide(p, s, self.cache)
        except Exception as e:
            p.setPen(QColor(180, 0, 0))
            p.drawText(QRectF(20, 20, self.deck.width - 40, 100), Qt.TextWordWrap, f"Could not render slide: {e}")
        p.restore()

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            self.window().zoom_by(1 if ev.angleDelta().y() > 0 else -1)
            ev.accept()
        else:
            super().wheelEvent(ev)


# --------------------------------------------------------------------------- presentation
class PresentWindow(QWidget):
    def __init__(self, deck: Deck, index: int, on_close):
        super().__init__()
        self.deck, self.index, self.on_close = deck, index, on_close
        self.mode = None  # None | "black" | "white"
        self.started = time.time()
        self.hud_until = time.time() + 2.5
        self.digits = ""
        self.cache: dict = {}
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setStyleSheet("background:black;")
        self.timer = QTimer(self, interval=500, timeout=self.update)
        self.timer.start()

    def start(self):
        self.showFullScreen()
        self.setFocus()

    def go(self, i):
        self.index = max(0, min(len(self.deck) - 1, i))
        self.mode = None
        self.hud_until = time.time() + 1.5
        self.update()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.close()
        elif k in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown, Qt.Key_Space, Qt.Key_N):
            self.go(self.index + 1)
        elif k in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp, Qt.Key_Backspace, Qt.Key_P):
            self.go(self.index - 1)
        elif k == Qt.Key_Home:
            self.go(0)
        elif k == Qt.Key_End:
            self.go(len(self.deck) - 1)
        elif k == Qt.Key_B:
            self.mode = None if self.mode == "black" else "black"
            self.update()
        elif k == Qt.Key_W:
            self.mode = None if self.mode == "white" else "white"
            self.update()
        elif Qt.Key_0 <= k <= Qt.Key_9:
            self.digits += chr(k)
        elif k in (Qt.Key_Return, Qt.Key_Enter) and self.digits:
            self.go(int(self.digits) - 1)
            self.digits = ""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.go(self.index + 1)
        elif e.button() == Qt.RightButton:
            self.go(self.index - 1)

    def wheelEvent(self, e):
        self.go(self.index + (1 if e.angleDelta().y() < 0 else -1))

    def mouseMoveEvent(self, e):
        self.unsetCursor()
        self.hud_until = time.time() + 2.5
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        if self.mode:
            p.fillRect(self.rect(), Qt.black if self.mode == "black" else Qt.white)
            return
        p.fillRect(self.rect(), Qt.black)
        W, H = self.deck.width, self.deck.height
        s = min(self.width() / W, self.height() / H)
        p.save()
        p.translate((self.width() - W * s) / 2, (self.height() - H * s) / 2)
        p.scale(s, s)
        sl = self.deck.slide(self.index)
        p.setClipRect(QRectF(0, 0, W, H))
        paint_background(p, sl, W, H)
        paint_slide(p, sl, self.cache)
        p.restore()
        if time.time() < self.hud_until:
            el = int(time.time() - self.started)
            txt = f"{self.index + 1} / {len(self.deck)}    {el // 60:02d}:{el % 60:02d}"
            p.setPen(Qt.white)
            r = QRectF(self.width() - 220, self.height() - 44, 200, 30)
            p.fillRect(r, QColor(0, 0, 0, 170))
            p.drawText(r, Qt.AlignCenter, txt)
        else:
            self.setCursor(Qt.BlankCursor)

    def closeEvent(self, e):
        self.timer.stop()
        self.on_close(self.index)
        super().closeEvent(e)


# --------------------------------------------------------------------------- main window
class MainWindow(DropOpenMixin, QMainWindow):
    drop_suffixes = (".pptx",)
    def __init__(self):
        super().__init__()
        self.settings = QSettings("PptxViewer", "PptxViewer")
        self.deck: Deck | None = None
        self.present: PresentWindow | None = None
        self.last_find = ""
        self.theme_mode = self.settings.value("theme", "system")
        self.setAcceptDrops(True)
        self.resize(1280, 800)
        self.setMinimumSize(720, 480)
        self._build()
        self._set_title()
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        self.sidebar.setVisible(self.settings.value("sidebar", True, type=bool))
        self.act_sidebar.setChecked(self.sidebar.isVisible())
        self._enable(False)

    # ---- ui
    def _build(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # empty state
        empty = QWidget()
        lay = QVBoxLayout(empty)
        lay.setAlignment(Qt.AlignCenter)
        t = QLabel("Open a PowerPoint presentation")
        f = t.font()
        f.setPointSize(18)
        f.setWeight(f.Weight.DemiBold)
        t.setFont(f)
        t.setAlignment(Qt.AlignCenter)
        s = QLabel("Drop a .pptx file here, or press Ctrl+O.\nFiles are opened locally and never uploaded.")
        s.setAlignment(Qt.AlignCenter)
        s.setForegroundRole(QPalette.PlaceholderText)
        b = QPushButton("Open .pptx…")
        b.setDefault(True)
        b.setMinimumHeight(36)
        b.clicked.connect(self.open_dialog)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumWidth(520)
        self.recent_list.setMaximumHeight(170)
        self.recent_list.itemActivated.connect(lambda it: self.open_file(it.data(Qt.UserRole)))
        self.recent_list.itemClicked.connect(lambda it: self.open_file(it.data(Qt.UserRole)))
        self.recent_title = QLabel("Recent")
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addSpacing(12)
        lay.addWidget(b, 0, Qt.AlignHCenter)
        lay.addSpacing(18)
        lay.addWidget(self.recent_title, 0, Qt.AlignHCenter)
        lay.addWidget(self.recent_list, 0, Qt.AlignHCenter)
        self.stack.addWidget(empty)

        # viewer
        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListView.IconMode)
        self.thumbs.setFlow(QListView.TopToBottom)
        self.thumbs.setWrapping(False)
        self.thumbs.setMovement(QListView.Static)
        self.thumbs.setResizeMode(QListView.Adjust)
        self.thumbs.setIconSize(QSize(THUMB_W, 100))
        self.thumbs.setSpacing(8)
        self.thumbs.setUniformItemSizes(True)
        self.thumbs.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.thumbs.setMinimumWidth(THUMB_W + 48)
        self.thumbs.setMaximumWidth(THUMB_W + 48)
        self.thumbs.currentRowChanged.connect(self.go_to)
        self.sidebar = self.thumbs

        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.canvas = SlideCanvas(self.scroll)
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)

        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText("No speaker notes on this slide.")
        self.notes.setMaximumHeight(160)
        self.notes.hide()

        right = QSplitter(Qt.Vertical)
        right.addWidget(self.scroll)
        right.addWidget(self.notes)
        right.setStretchFactor(0, 1)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.thumbs)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setChildrenCollapsible(False)
        self.stack.addWidget(split)

        # status bar
        self.sb_left = QLabel("Ready")
        self.sb_zoom = QLabel("")
        self.statusBar().addWidget(self.sb_left, 1)
        self.statusBar().addPermanentWidget(self.sb_zoom)

        self._actions()
        self._refresh_recent()

    def _act(self, text, slot, shortcut=None, tip=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut) if isinstance(shortcut, str) else shortcut)
        if tip:
            a.setStatusTip(tip)
            a.setToolTip(f"{text.replace('&', '')} ({a.shortcut().toString(QKeySequence.NativeText)})" if shortcut else tip)
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        self.addAction(a)
        return a

    def _actions(self):
        mb = self.menuBar()
        # File
        m = mb.addMenu("&File")
        self.act_open = self._act("&Open…", self.open_dialog, QKeySequence.Open, "Open a presentation")
        m.addAction(self.act_open)
        self.recent_menu = m.addMenu("Open &Recent")
        self.act_close = self._act("&Close presentation", self.close_deck, QKeySequence.Close)
        m.addAction(self.act_close)
        m.addSeparator()
        self.act_png = self._act("Export slide as &PNG…", self.export_png, "Ctrl+Shift+S", "Save the current slide as an image")
        self.act_pdf = self._act("Export all as P&DF…", self.export_pdf, "Ctrl+Shift+E", "Save every slide to a PDF")
        self.act_copy = self._act("&Copy slide image", self.copy_slide, "Ctrl+Shift+C")
        for a in (self.act_png, self.act_pdf, self.act_copy):
            m.addAction(a)
        m.addSeparator()
        self.act_assoc = self._act("Add to “Open with” list", self.register_open_with, None,
                                   "Lets Windows offer PPTX Viewer for .pptx files")
        m.addAction(self.act_assoc)
        m.addSeparator()
        m.addAction(self._act("E&xit", self.close, "Ctrl+Q"))

        # Edit
        m = mb.addMenu("&Edit")
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find in slides…")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMaximumWidth(220)
        self.find_edit.returnPressed.connect(lambda: self.find(1))
        self.act_find = self._act("&Find…", lambda: (self.find_edit.setFocus(), self.find_edit.selectAll()), QKeySequence.Find)
        self.act_next = self._act("Find &next", lambda: self.find(1), "F3")
        self.act_prevm = self._act("Find &previous", lambda: self.find(-1), "Shift+F3")
        for a in (self.act_find, self.act_next, self.act_prevm):
            m.addAction(a)

        # View
        m = mb.addMenu("&View")
        self.act_zin = self._act("Zoom &in", lambda: self.zoom_by(1), "Ctrl+=")
        self.act_zout = self._act("Zoom &out", lambda: self.zoom_by(-1), "Ctrl+-")
        self.act_fit = self._act("&Fit to window", lambda: self.set_zoom(None), "Ctrl+0")
        self.act_100 = self._act("&Actual size (100%)", lambda: self.set_zoom(1.0), "Ctrl+1")
        self.act_sidebar = self._act("&Slide list", self.toggle_sidebar, "F4", checkable=True)
        self.act_notes = self._act("Speaker &notes", self.toggle_notes, "Ctrl+Shift+N", checkable=True)
        for a in (self.act_zin, self.act_zout, self.act_fit, self.act_100):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.act_sidebar)
        m.addAction(self.act_notes)
        m.addSeparator()
        tm = m.addMenu("&Theme")
        grp = QActionGroup(self)
        for label, mode in (("&System", "system"), ("&Light", "light"), ("&Dark", "dark")):
            a = QAction(label, self, checkable=True)
            a.setChecked(self.theme_mode == mode)
            a.triggered.connect(lambda _=False, md=mode: self.set_theme(md))
            grp.addAction(a)
            tm.addAction(a)

        # Slide
        m = mb.addMenu("&Slide")
        self.act_first = self._act("&First", lambda: self.go_to(0), "Home")
        self.act_prev = self._act("&Previous", lambda: self.go_to(self.cur - 1), Qt.Key_Left)
        self.act_nextslide = self._act("&Next", lambda: self.go_to(self.cur + 1), Qt.Key_Right)
        self.act_last = self._act("&Last", lambda: self.go_to(len(self.deck) - 1), "End")
        self.act_goto = self._act("&Go to slide…", self.goto_dialog, "Ctrl+G")
        self.act_pgup = self._act("Previous (PgUp)", lambda: self.go_to(self.cur - 1), Qt.Key_PageUp)
        self.act_pgdn = self._act("Next (PgDn)", lambda: self.go_to(self.cur + 1), Qt.Key_PageDown)
        for a in (self.act_first, self.act_prev, self.act_nextslide, self.act_last, self.act_goto):
            m.addAction(a)
        m.addSeparator()
        self.act_show = self._act("Start &presentation", lambda: self.start_present(0), "F5", "Present from the first slide")
        self.act_show_cur = self._act("Present from c&urrent slide", lambda: self.start_present(self.cur), "Shift+F5")
        m.addAction(self.act_show)
        m.addAction(self.act_show_cur)

        # Help
        m = mb.addMenu("&Help")
        m.addAction(self._act("&Keyboard shortcuts", self.show_shortcuts, "F1"))
        m.addAction(self._act("&About", self.show_about))

        # Toolbar
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)
        tb.addAction(self.act_open)
        tb.addSeparator()
        self.page = QSpinBox()
        self.page.setMinimum(1)
        self.page.setKeyboardTracking(False)
        self.page.setFixedWidth(64)
        self.page.valueChanged.connect(lambda v: self.go_to(v - 1))
        self.page_total = QLabel(" / –  ")
        for a, txt in ((self.act_prev, "‹"), (self.act_nextslide, "›")):
            pass
        b1 = QPushButton("‹")
        b1.setFixedWidth(30)
        b1.setToolTip("Previous slide (Left)")
        b1.clicked.connect(lambda: self.go_to(self.cur - 1))
        b2 = QPushButton("›")
        b2.setFixedWidth(30)
        b2.setToolTip("Next slide (Right)")
        b2.clicked.connect(lambda: self.go_to(self.cur + 1))
        self.nav_widgets = [b1, b2, self.page]
        tb.addWidget(b1)
        tb.addWidget(self.page)
        tb.addWidget(self.page_total)
        tb.addWidget(b2)
        tb.addSeparator()
        tb.addAction(self.act_zout)
        tb.addAction(self.act_fit)
        tb.addAction(self.act_zin)
        tb.addSeparator()
        tb.addAction(self.act_notes)
        tb.addAction(self.act_show)
        sp = QWidget()
        sp.setSizePolicy(sp.sizePolicy().horizontalPolicy().Expanding, sp.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(sp)
        tb.addWidget(self.find_edit)
        self.toolbar = tb
        self._viewer_actions = [self.act_close, self.act_png, self.act_pdf, self.act_copy, self.act_find, self.act_next,
                                self.act_prevm, self.act_zin, self.act_zout, self.act_fit, self.act_100, self.act_sidebar,
                                self.act_notes, self.act_first, self.act_prev, self.act_nextslide, self.act_last,
                                self.act_goto, self.act_show, self.act_show_cur, self.act_pgup, self.act_pgdn]

    def _enable(self, on: bool):
        for a in self._viewer_actions:
            a.setEnabled(on)
        for w in self.nav_widgets + [self.find_edit]:
            w.setEnabled(on)

    # ---- state helpers
    cur = 0

    def _set_title(self):
        n = Path(self.deck.filename).name if self.deck else None
        self.setWindowTitle(f"{n} — {APP_NAME}" if n else APP_NAME)

    def _update_status(self):
        if not self.deck:
            self.sb_left.setText("Ready")
            self.sb_zoom.setText("")
            return
        self.sb_left.setText(f"Slide {self.cur + 1} of {len(self.deck)}    ·    "
                             f"{self.deck.width / 96:.2f} × {self.deck.height / 96:.2f} in")
        self.sb_zoom.setText(("Fit  " if self.canvas.zoom is None else "") + f"{round(self.canvas.scale * 100)}%  ")

    # ---- open / close
    def open_dialog(self):
        start = self.settings.value("last_dir", str(Path.home()))
        fn, _ = QFileDialog.getOpenFileName(self, "Open presentation", start, "PowerPoint presentations (*.pptx)")
        if fn:
            self.open_file(fn)

    def open_file(self, fn: str):
        fn = str(Path(fn))
        if Path(fn).suffix.lower() != ".pptx":
            QMessageBox.warning(self, APP_NAME, f"“{Path(fn).name}” is not a .pptx file.\n\nOnly PowerPoint .pptx presentations are supported.")
            return
        if not Path(fn).exists():
            QMessageBox.warning(self, APP_NAME, f"File not found:\n{fn}")
            self._forget_recent(fn)
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            deck = Deck(fn)
        except PptxError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_NAME, f"Could not open “{Path(fn).name}”.\n\n{e}")
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_NAME, f"Could not open “{Path(fn).name}”.\n\nIt may be corrupt or password-protected.\n({e})")
            return
        QApplication.restoreOverrideCursor()
        self.deck = deck
        self.settings.setValue("last_dir", str(Path(fn).parent))
        self._push_recent(fn)
        self._set_title()
        self.page.blockSignals(True)
        self.page.setMaximum(len(deck))
        self.page.blockSignals(False)
        self.page_total.setText(f" / {len(deck)}  ")
        self._enable(True)
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        blank = QPixmap(THUMB_W, int(THUMB_W * deck.height / deck.width))
        blank.fill(QColor(255, 255, 255))
        for i in range(len(deck)):
            it = QListWidgetItem(QIcon(blank), str(i + 1))
            it.setTextAlignment(Qt.AlignHCenter)
            self.thumbs.addItem(it)
        self.thumbs.setIconSize(blank.size())
        self.thumbs.blockSignals(False)
        self.canvas.set_deck(deck)
        self.stack.setCurrentIndex(1)
        last = int(self.settings.value("pos/" + fn, 0) or 0)
        self.cur = -1
        self.go_to(min(last, len(deck) - 1))
        self._thumb_job = 0
        QTimer.singleShot(0, self._render_thumbs)
        self.activateWindow()

    def _render_thumbs(self):
        deck = self.deck
        if not deck or self._thumb_job >= len(deck):
            return
        i = self._thumb_job
        self._thumb_job += 1
        pm = render_pixmap(deck, i, THUMB_W * 2)
        pm.setDevicePixelRatio(2.0)
        it = self.thumbs.item(i)
        if it is not None:
            it.setIcon(QIcon(pm))
        QTimer.singleShot(0, self._render_thumbs)

    def close_deck(self):
        self._save_pos()
        self.deck = None
        self._thumb_job = 10**9
        self.thumbs.clear()
        self.canvas.set_deck(None)
        self.stack.setCurrentIndex(0)
        self._enable(False)
        self._set_title()
        self._update_status()
        self._refresh_recent()

    def _save_pos(self):
        if self.deck:
            self.settings.setValue("pos/" + self.deck.filename, self.cur)

    # ---- recents
    def _recents(self) -> list:
        v = self.settings.value("recent", [])
        return [x for x in (v if isinstance(v, list) else [v]) if x]

    def _push_recent(self, fn):
        r = [x for x in self._recents() if x != fn]
        self.settings.setValue("recent", ([fn] + r)[:10])
        self._refresh_recent()

    def _forget_recent(self, fn):
        self.settings.setValue("recent", [x for x in self._recents() if x != fn])
        self._refresh_recent()

    def _refresh_recent(self):
        self.recent_menu.clear()
        self.recent_list.clear()
        r = [x for x in self._recents() if Path(x).exists()]
        for fn in r:
            self.recent_menu.addAction(Path(fn).name, lambda f=fn: self.open_file(f)).setStatusTip(fn)
            it = QListWidgetItem(f"{Path(fn).name}    —    {Path(fn).parent}")
            it.setData(Qt.UserRole, fn)
            self.recent_list.addItem(it)
        if r:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction("Clear list", lambda: (self.settings.setValue("recent", []), self._refresh_recent()))
        self.recent_menu.setEnabled(bool(r))
        self.recent_list.setVisible(bool(r))
        self.recent_title.setVisible(bool(r))

    # ---- navigation
    def go_to(self, i: int):
        if not self.deck:
            return
        i = max(0, min(len(self.deck) - 1, i))
        if i == self.cur:
            return
        self.cur = i
        self.canvas.set_index(i)
        for w, v in ((self.thumbs, None),):
            self.thumbs.blockSignals(True)
            self.thumbs.setCurrentRow(i)
            self.thumbs.blockSignals(False)
        self.page.blockSignals(True)
        self.page.setValue(i + 1)
        self.page.blockSignals(False)
        try:
            self.notes.setPlainText(self.deck.slide(i).notes)
        except Exception:
            self.notes.clear()
        self.scroll.verticalScrollBar().setValue(0)
        self._update_status()

    def goto_dialog(self):
        from PySide6.QtWidgets import QInputDialog
        v, ok = QInputDialog.getInt(self, "Go to slide", f"Slide number (1–{len(self.deck)}):", self.cur + 1, 1, len(self.deck))
        if ok:
            self.go_to(v - 1)

    def find(self, step=1):
        if not self.deck:
            return
        q = self.find_edit.text().strip().lower()
        if not q:
            return
        n = len(self.deck)
        start = self.cur + step if q == self.last_find else self.cur
        self.last_find = q
        for k in range(n):
            i = (start + step * k) % n
            if q in self.deck.text(i).lower():
                self.go_to(i)
                self.statusBar().showMessage(f"“{q}” found on slide {i + 1}", 3000)
                return
        self.statusBar().showMessage(f"“{q}” not found", 3000)

    # ---- zoom / panels
    def set_zoom(self, z):
        self.canvas.zoom = z
        self.canvas.relayout()
        self._update_status()

    def zoom_by(self, d):
        if not self.deck:
            return
        cur = self.canvas.scale
        if d > 0:
            nxt = next((z for z in ZOOM_STEPS if z > cur + 1e-3), ZOOM_STEPS[-1])
        else:
            nxt = next((z for z in reversed(ZOOM_STEPS) if z < cur - 1e-3), ZOOM_STEPS[0])
        self.set_zoom(nxt)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())
        self.act_sidebar.setChecked(self.sidebar.isVisible())

    def toggle_notes(self):
        self.notes.setVisible(not self.notes.isVisible())
        self.act_notes.setChecked(self.notes.isVisible())

    def set_theme(self, mode):
        self.theme_mode = mode
        self.settings.setValue("theme", mode)
        self.canvas.dark = apply_theme(QApplication.instance(), mode)
        self.canvas.update()

    # ---- export
    def _stem(self):
        return Path(self.deck.filename).stem

    def export_png(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export slide", f"{self._stem()}-slide{self.cur + 1}.png", "PNG image (*.png)")
        if fn:
            render_pixmap(self.deck, self.cur, int(self.deck.width * 2)).save(fn, "PNG")
            self.statusBar().showMessage(f"Saved {fn}", 4000)

    def copy_slide(self):
        QGuiApplication.clipboard().setPixmap(render_pixmap(self.deck, self.cur, int(self.deck.width * 2)))
        self.statusBar().showMessage("Slide copied to clipboard", 3000)

    def export_pdf(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export PDF", f"{self._stem()}.pdf", "PDF document (*.pdf)")
        if not fn:
            return
        d = self.deck
        w = QPdfWriter(fn)
        w.setResolution(96)
        w.setPageSize(QPageSize(QSizeF(d.width * 0.75, d.height * 0.75), QPageSize.Point))
        w.setPageMargins(__import__("PySide6.QtCore", fromlist=["QMarginsF"]).QMarginsF(0, 0, 0, 0))
        p = QPainter(w)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for i in range(len(d)):
                if i:
                    w.newPage()
                s = d.slide(i)
                paint_background(p, s, d.width, d.height)
                paint_slide(p, s, {})
        finally:
            p.end()
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"Saved {fn}", 4000)

    # ---- presentation
    def start_present(self, index):
        if not self.deck or self.present:
            return
        self.present = PresentWindow(self.deck, index, self._present_closed)
        self.present.start()

    def _present_closed(self, index):
        self.present = None
        self.go_to(index)
        self.activateWindow()

    # ---- misc
    def register_open_with(self):
        if not getattr(sys, "frozen", False):
            QMessageBox.information(self, APP_NAME, "This works from the packaged PPTX Viewer.exe.")
            return
        try:
            import winreg
            exe = sys.executable
            base = r"Software\Classes\Applications\PPTX Viewer.exe"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
                winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, APP_NAME)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe}" "%1"')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\SupportedTypes") as k:
                winreg.SetValueEx(k, ".pptx", 0, winreg.REG_SZ, "")
            QMessageBox.information(self, APP_NAME, "Done. Right-click a .pptx → Open with → Choose another app → "
                                    "PPTX Viewer (tick “Always” to make it the default).")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Could not update the registry:\n{e}")

    def show_shortcuts(self):
        QMessageBox.information(self, "Keyboard shortcuts", (
            "Ctrl+O  Open\nCtrl+W  Close presentation\nCtrl+F / F3  Find / next match\n"
            "← → PgUp PgDn Home End  Navigate\nCtrl+G  Go to slide\n"
            "Ctrl+= / Ctrl+- / Ctrl+0 / Ctrl+1  Zoom in / out / fit / 100%\nCtrl+wheel  Zoom\n"
            "F4  Slide list      Ctrl+Shift+N  Speaker notes\n"
            "F5  Present  ·  Shift+F5  Present from current\n"
            "While presenting: Space/→ next, ← back, B black, W white, number+Enter jump, Esc exit\n"
            "Ctrl+Shift+S  Export slide PNG   Ctrl+Shift+E  Export PDF"))

    def show_about(self):
        QMessageBox.about(self, APP_NAME, f"<b>{APP_NAME}</b><br>A fast, offline .pptx viewer.<br><br>"
                          "Native Qt app. Files never leave your computer.<br><br>"
                          "Not rendered: charts, SmartArt, animations, embedded media.")

    # ---- events
    def closeEvent(self, e):
        self._save_pos()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("sidebar", self.sidebar.isVisible())
        if self.present:
            self.present.close()
        super().closeEvent(e)
