"""Enhanced QTableView with professional styling and features."""
from typing import Tuple
from PySide6.QtWidgets import QTableView, QApplication, QHeaderView, QAbstractItemView, QMenu
from PySide6.QtCore import Qt, QModelIndex, Signal
from PySide6.QtGui import QClipboard, QColor, QPalette
import csv
import io


class CsvTableView(QTableView):
    """Professional table view with alternating rows, context menus, and copy/paste."""

    selection_stats_changed = Signal(dict)  # {sum, avg, count, cell_count}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize table view with professional styling."""
        # Selection
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setAlternatingRowColors(True)  # Alternating row colors for better readability

        # Style alternating rows
        self.setStyleSheet("""
            QTableView {
                gridline-color: #ddd;
                background-color: white;
            }
            QTableView::item {
                padding: 4px;
                border: none;
                background-color: white;
            }
            QTableView::item:alternate {
                background-color: #f5f5f5;
            }
            QTableView::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTableView::item:hover {
                background-color: #e8f0fe;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)

        # Headers
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionsMovable(True)  # Allow column reordering
        self.verticalHeader().setVisible(True)

        # Row height
        self.verticalHeader().setDefaultSectionSize(24)

        # Resize columns on double-click
        self.horizontalHeader().sectionDoubleClicked.connect(self.on_header_double_click)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # Enable copy on Ctrl+C
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.keyPressEvent = self.on_key_press

    def setModel(self, model):
        """Override setModel to connect selection tracking."""
        super().setModel(model)
        if self.selectionModel():
            self.selectionModel().selectionChanged.connect(self.on_selection_changed)

    def on_key_press(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self.copy_selection()
        elif event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            self.paste_selection()
        elif event.key() == Qt.Key_Delete:
            self.delete_selection()
        elif event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.selectAll()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, position):
        """Show context menu on right-click."""
        menu = QMenu(self)

        # Copy option
        menu.addAction("📋 Copy").triggered.connect(self.copy_selection)
        menu.addAction("📋 Copy with Headers").triggered.connect(self.copy_with_headers)

        menu.addSeparator()

        # Paste option
        menu.addAction("📌 Paste").triggered.connect(self.paste_selection)

        menu.addSeparator()

        # Delete option
        menu.addAction("🗑️ Delete").triggered.connect(self.delete_selection)

        menu.addSeparator()

        # Insert/delete rows/columns
        menu.addAction("➕ Insert Row Above").triggered.connect(self.insert_row_above)
        menu.addAction("➕ Insert Row Below").triggered.connect(self.insert_row_below)
        menu.addAction("➕ Insert Column Left").triggered.connect(self.insert_column_left)
        menu.addAction("➕ Insert Column Right").triggered.connect(self.insert_column_right)

        menu.addSeparator()

        menu.addAction("❌ Delete Row").triggered.connect(self.delete_row)
        menu.addAction("❌ Delete Column").triggered.connect(self.delete_column)

        menu.exec(self.mapToGlobal(position))

    def copy_selection(self):
        """Copy selected cells as TSV."""
        selection = self.selectionModel().selection()
        if not selection:
            return

        # Get bounding box
        min_row, max_row = float('inf'), -1
        min_col, max_col = float('inf'), -1

        for range_ in selection:
            for idx in range_.indexes():
                min_row = min(min_row, idx.row())
                max_row = max(max_row, idx.row())
                min_col = min(min_col, idx.column())
                max_col = max(max_col, idx.column())

        if min_row > max_row or min_col > max_col:
            return

        # Build TSV
        lines = []
        for row in range(int(min_row), int(max_row) + 1):
            cells = []
            for col in range(int(min_col), int(max_col) + 1):
                idx = self.model().index(row, col)
                value = self.model().data(idx) or ""
                # Quote cells with special characters
                if "\t" in str(value) or "\n" in str(value) or '"' in str(value):
                    value = '"' + str(value).replace('"', '""') + '"'
                cells.append(str(value))
            lines.append("\t".join(cells))

        text = "\n".join(lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(text, QClipboard.Clipboard)

    def copy_with_headers(self):
        """Copy with column headers."""
        model = self.model()
        if not model or model.rowCount() == 0:
            self.copy_selection()
            return

        # Add header row
        headers = []
        for col in range(model.columnCount()):
            header_text = model.headerData(col, Qt.Horizontal)
            headers.append(str(header_text or ""))

        # Get selection and prepend headers
        selection = self.selectionModel().selection()
        if not selection:
            return

        min_col, max_col = float('inf'), -1
        for range_ in selection:
            for idx in range_.indexes():
                min_col = min(min_col, idx.column())
                max_col = max(max_col, idx.column())

        header_line = "\t".join(headers[int(min_col):int(max_col)+1])

        self.copy_selection()
        current = QApplication.clipboard().text()
        QApplication.clipboard().setText(header_line + "\n" + current, QClipboard.Clipboard)

    def paste_selection(self):
        """Paste from clipboard."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        model = self.model()
        current = self.currentIndex()
        if not current.isValid():
            return

        # Parse TSV
        rows = [row.split("\t") for row in text.split("\n") if row.strip()]
        for r_offset, row in enumerate(rows):
            for c_offset, value in enumerate(row):
                idx = model.index(current.row() + r_offset, current.column() + c_offset)
                if idx.isValid():
                    model.setData(idx, value)

    def delete_selection(self):
        """Delete selected cells."""
        selection = self.selectionModel().selection()
        model = self.model()

        for range_ in selection:
            for idx in range_.indexes():
                if idx.isValid():
                    model.setData(idx, "")

    def insert_row_above(self):
        """Insert row above current."""
        current = self.currentIndex()
        if current.isValid():
            self.model().insertRows(current.row(), 1)

    def insert_row_below(self):
        """Insert row below current."""
        current = self.currentIndex()
        if current.isValid():
            self.model().insertRows(current.row() + 1, 1)

    def insert_column_left(self):
        """Insert column to the left."""
        current = self.currentIndex()
        if current.isValid():
            self.model().insertColumns(current.column(), 1)

    def insert_column_right(self):
        """Insert column to the right."""
        current = self.currentIndex()
        if current.isValid():
            self.model().insertColumns(current.column() + 1, 1)

    def delete_row(self):
        """Delete current row."""
        current = self.currentIndex()
        if current.isValid():
            self.model().removeRows(current.row(), 1)

    def delete_column(self):
        """Delete current column."""
        current = self.currentIndex()
        if current.isValid():
            self.model().removeColumns(current.column(), 1)

    def on_header_double_click(self, logical_index: int):
        """Auto-fit column width on header double-click."""
        model = self.model()
        visible_rows = min(100, model.rowCount())

        max_width = self.fontMetrics().width("W" * 15)
        for row in range(visible_rows):
            idx = model.index(row, logical_index)
            value = model.data(idx) or ""
            width = self.fontMetrics().width(str(value))
            max_width = max(max_width, width)

        self.setColumnWidth(logical_index, min(max_width + 10, 500))

    def on_selection_changed(self):
        """Update selection stats."""
        selection = self.selectionModel().selection()

        numeric_values = []
        cell_count = 0

        for range_ in selection:
            for idx in range_.indexes():
                cell_count += 1
                value = self.model().data(idx) or ""
                try:
                    num = float(str(value).replace(",", "."))
                    numeric_values.append(num)
                except (ValueError, TypeError):
                    pass

        stats = {
            "sum": sum(numeric_values) if numeric_values else 0,
            "avg": sum(numeric_values) / len(numeric_values) if numeric_values else 0,
            "count": len(numeric_values),
            "cell_count": cell_count,
        }

        self.selection_stats_changed.emit(stats)
