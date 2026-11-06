"""Enhanced main application window - Fixed version."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMessageBox, QFileDialog,
    QVBoxLayout, QWidget, QProgressBar, QLabel, QToolBar
)
from PySide6.QtCore import Qt, QThread, QSettings, QSize
from PySide6.QtGui import QKeySequence, QIcon, QFont
from viewing_core import DropOpenMixin
from ..loader import load_csv_async, save_csv
from ..model import CsvTableModel, CsvSortFilterProxyModel
from .csv_tab import CsvTab
from .theme import sync_theme_to_windows


class MainWindow(DropOpenMixin, QMainWindow):
    """Professional main application window."""
    drop_suffixes = (".csv",)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("CsvViewer", "CsvViewer")
        self.open_files = {}
        self.current_font_size = 10

        self.setWindowTitle("CSV Viewer - Professional Edition")
        self.setMinimumSize(1000, 700)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.setCentralWidget(self.tab_widget)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("QStatusBar { padding: 4px; }")
        self.setStatusBar(self.status_bar)

        self.info_label = QLabel("Ready")
        self.info_label.setStyleSheet("color: #666; font-size: 10px;")
        self.status_bar.addWidget(self.info_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("color: #666; font-size: 10px; padding-right: 10px;")
        self.status_bar.addPermanentWidget(self.file_info_label)

        self.create_menus()
        self.create_toolbars()
        self.restore_geometry()
        sync_theme_to_windows(self)

        self.showMaximized()

    def create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()
        menubar.setStyleSheet("QMenuBar { padding: 2px; }")

        # FILE MENU
        file_menu = menubar.addMenu("File")

        open_action = file_menu.addAction("Open...")
        open_action.setShortcut(QKeySequence.Open)
        open_action.setStatusTip("Open a CSV file (Ctrl+O)")
        open_action.triggered.connect(self.on_open_file)

        self.recent_menu = file_menu.addMenu("Recent Files")
        file_menu.addSeparator()

        save_action = file_menu.addAction("Save")
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip("Save current file (Ctrl+S)")
        save_action.triggered.connect(self.on_save_file)

        save_as_action = file_menu.addAction("Save As...")
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.setStatusTip("Save with a new name (Ctrl+Shift+S)")
        save_as_action.triggered.connect(self.on_save_as_file)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setStatusTip("Close the application (Ctrl+Q)")
        exit_action.triggered.connect(self.close)

        # EDIT MENU
        edit_menu = menubar.addMenu("Edit")

        find_action = edit_menu.addAction("Find...")
        find_action.setShortcut(QKeySequence.Find)
        find_action.setStatusTip("Find text (Ctrl+F)")
        find_action.triggered.connect(self.on_find)

        find_replace_action = edit_menu.addAction("Find & Replace...")
        find_replace_action.setShortcut(QKeySequence("Ctrl+H"))
        find_replace_action.setStatusTip("Find and replace text (Ctrl+H)")
        find_replace_action.triggered.connect(self.on_find_replace)

        edit_menu.addSeparator()

        select_all_action = edit_menu.addAction("Select All")
        select_all_action.setShortcut(QKeySequence.SelectAll)
        select_all_action.setStatusTip("Select all cells (Ctrl+A)")
        select_all_action.triggered.connect(self.on_select_all)

        # VIEW MENU
        view_menu = menubar.addMenu("View")

        zoom_in_action = view_menu.addAction("Zoom In")
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.setStatusTip("Increase text size (Ctrl++)")
        zoom_in_action.triggered.connect(self.on_zoom_in)

        zoom_out_action = view_menu.addAction("Zoom Out")
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.setStatusTip("Decrease text size (Ctrl+-)")
        zoom_out_action.triggered.connect(self.on_zoom_out)

        self.update_recent_files_menu()

    def create_toolbars(self):
        """Create toolbars."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        toolbar.addAction("Open").triggered.connect(self.on_open_file)
        toolbar.addAction("Save").triggered.connect(self.on_save_file)
        toolbar.addSeparator()
        toolbar.addAction("Find").triggered.connect(self.on_find)

    def on_open_file(self):
        """Open file dialog."""
        last_dir = self.settings.value("last_open_dir", str(Path.home()))
        filepaths, _ = QFileDialog.getOpenFileNames(
            self, "Open CSV Files", last_dir, "CSV Files (*.csv);;All Files (*)"
        )
        if filepaths:
            self.settings.setValue("last_open_dir", str(Path(filepaths[0]).parent))
            for filepath in filepaths:
                self.open_file(filepath)

    def open_file(self, filepath: str):
        """Open a CSV file."""
        filepath = str(Path(filepath).absolute())

        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, CsvTab) and tab.filepath == filepath:
                self.tab_widget.setCurrentIndex(i)
                self.info_label.setText(f"File already open: {Path(filepath).name}")
                return

        tab = CsvTab(filepath)
        model = tab.get_model().source_model()
        tab.file_modified.connect(self.on_file_modified)

        index = self.tab_widget.addTab(tab, Path(filepath).name)
        self.tab_widget.setCurrentIndex(index)

        self.info_label.setText(f"Loading: {Path(filepath).name}...")
        self.progress_bar.show()
        self.progress_bar.setValue(0)

        thread, worker = load_csv_async(filepath)
        self.open_files[filepath] = (thread, worker)

        worker.progress.connect(self.on_load_progress)
        worker.finished.connect(lambda rows, enc, delim, lt, path: self.on_load_finished(
            rows, enc, delim, lt, path, model, tab
        ))
        worker.error.connect(self.on_load_error)

    def on_load_progress(self, percent: int):
        """Update load progress."""
        self.progress_bar.setValue(percent)

    def on_load_finished(self, rows, encoding, delimiter, line_terminator, filepath, model, tab):
        """Handle load completion."""
        model.set_data_from_rows(rows, encoding, delimiter, line_terminator, filepath)

        tab.delimiter_combo.blockSignals(True)
        tab.encoding_combo.blockSignals(True)

        if delimiter == ",":
            tab.delimiter_combo.setCurrentText(",")
        elif delimiter == ";":
            tab.delimiter_combo.setCurrentText(";")
        elif delimiter == "\t":
            tab.delimiter_combo.setCurrentText("Tab")
        elif delimiter == "|":
            tab.delimiter_combo.setCurrentText("|")

        enc_map = {
            "utf-8": "UTF-8",
            "utf-8-sig": "UTF-8 BOM",
            "windows-1252": "Windows-1252",
            "windows-1250": "Windows-1250",
        }
        tab.encoding_combo.setCurrentText(enc_map.get(encoding, "UTF-8"))

        tab.delimiter_combo.blockSignals(False)
        tab.encoding_combo.blockSignals(False)

        self.update_status_bar()
        self.progress_bar.hide()
        self.info_label.setText(f"Loaded: {Path(filepath).name}")

        self.add_recent_file(filepath)

    def on_load_error(self, error_msg: str):
        """Handle load error."""
        self.info_label.setText(f"Error loading file")
        QMessageBox.critical(self, "Error Loading File", error_msg)
        self.progress_bar.hide()

    def update_status_bar(self):
        """Update status bar."""
        current_tab = self.tab_widget.currentWidget()
        if not isinstance(current_tab, CsvTab):
            return

        model = current_tab.get_model().source_model()
        row_count = model.rowCount()
        col_count = model.columnCount()

        info = f"Rows: {row_count:,} | Cols: {col_count} | {model.encoding} | Delim: {repr(model.delimiter)}"
        self.file_info_label.setText(info)

    def on_file_modified(self, filepath: str, modified: bool):
        """Handle file modified."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, CsvTab) and tab.filepath == filepath:
                title = Path(filepath).name
                if modified:
                    title = "● " + title
                self.tab_widget.setTabText(i, title)
                break

    def on_save_file(self):
        """Save current file."""
        current_tab = self.tab_widget.currentWidget()
        if not isinstance(current_tab, CsvTab):
            return

        model = current_tab.get_model().source_model()
        if not model.is_modified():
            self.info_label.setText("No changes to save")
            return

        success = save_csv(
            model.filepath,
            model.all_rows(),
            model.encoding,
            model.delimiter,
            model.line_terminator,
        )

        if success:
            model.set_modified(False)
            self.info_label.setText(f"Saved: {Path(model.filepath).name}")
        else:
            QMessageBox.critical(self, "Error", "Failed to save file.")

    def on_save_as_file(self):
        """Save as."""
        current_tab = self.tab_widget.currentWidget()
        if not isinstance(current_tab, CsvTab):
            return

        last_dir = self.settings.value("last_save_dir", str(Path.home()))
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save As", last_dir, "CSV Files (*.csv);;All Files (*)"
        )
        if not filepath:
            return

        self.settings.setValue("last_save_dir", str(Path(filepath).parent))

        model = current_tab.get_model().source_model()
        success = save_csv(
            filepath,
            model.all_rows(),
            model.encoding,
            model.delimiter,
            model.line_terminator,
        )

        if success:
            model.filepath = filepath
            model.set_modified(False)
            current_tab.filepath = filepath
            self.tab_widget.setTabText(self.tab_widget.currentIndex(), Path(filepath).name)
            self.info_label.setText(f"Saved as: {Path(filepath).name}")
        else:
            QMessageBox.critical(self, "Error", "Failed to save file.")

    def on_find(self):
        """Show find bar."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, CsvTab):
            current_tab.show_find_bar()
            self.info_label.setText("Find mode - press Enter or click Next")

    def on_find_replace(self):
        """Find and replace."""
        self.info_label.setText("Find & Replace feature coming soon")
        QMessageBox.information(self, "Feature Preview", "Find & Replace coming soon!")

    def on_select_all(self):
        """Select all."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, CsvTab):
            current_tab.table_view.selectAll()
            self.info_label.setText("All cells selected")

    def on_zoom_in(self):
        """Zoom in."""
        self.current_font_size = min(self.current_font_size + 1, 16)
        self._apply_font_size()

    def on_zoom_out(self):
        """Zoom out."""
        self.current_font_size = max(self.current_font_size - 1, 8)
        self._apply_font_size()

    def _apply_font_size(self):
        """Apply font size."""
        font = QFont()
        font.setPointSize(self.current_font_size)
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, CsvTab):
                tab.table_view.setFont(font)
        self.info_label.setText(f"Font size: {self.current_font_size}pt")

    def on_tab_close_requested(self, index: int):
        """Handle tab close."""
        tab = self.tab_widget.widget(index)
        if not isinstance(tab, CsvTab):
            self.tab_widget.removeTab(index)
            return

        model = tab.get_model().source_model()
        if model.is_modified():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to {Path(tab.filepath).name}?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self.on_save_file()
            elif reply == QMessageBox.Cancel:
                return

        self.tab_widget.removeTab(index)
        if tab.filepath in self.open_files:
            thread, _ = self.open_files.pop(tab.filepath)
            thread.quit()
            thread.wait()

    def add_recent_file(self, filepath: str):
        """Add recent file."""
        recent = self.settings.value("recent_files", [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif not isinstance(recent, list):
            recent = []

        if filepath in recent:
            recent.remove(filepath)
        recent.insert(0, filepath)
        recent = recent[:10]
        self.settings.setValue("recent_files", recent)
        self.update_recent_files_menu()

    def update_recent_files_menu(self):
        """Update recent files menu."""
        self.recent_menu.clear()
        recent = self.settings.value("recent_files", [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif not isinstance(recent, list):
            recent = []

        if not recent:
            self.recent_menu.addAction("(No recent files)").setEnabled(False)
            return

        for filepath in recent:
            if Path(filepath).exists():
                action = self.recent_menu.addAction(Path(filepath).name)
                action.setToolTip(filepath)
                action.triggered.connect(lambda checked, f=filepath: self.open_file(f))
            else:
                recent.remove(filepath)

        if recent:
            self.settings.setValue("recent_files", recent)

    def restore_geometry(self):
        """Restore window geometry."""
        geometry = self.settings.value("geometry")
        state = self.settings.value("windowstate")
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def save_geometry(self):
        """Save window geometry."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowstate", self.saveState())

    def closeEvent(self, event):
        """Handle close."""
        unsaved_count = 0
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, CsvTab):
                if tab.get_model().source_model().is_modified():
                    unsaved_count += 1

        if unsaved_count > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have {unsaved_count} file(s) with unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Save:
                for i in range(self.tab_widget.count()):
                    self.tab_widget.setCurrentIndex(i)
                    self.on_save_file()

        for thread, _ in self.open_files.values():
            thread.quit()
            thread.wait()

        self.save_geometry()
        event.accept()
