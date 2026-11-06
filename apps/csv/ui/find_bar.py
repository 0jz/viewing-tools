"""Find toolbar for searching CSV contents."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QComboBox
from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence


class FindBar(QWidget):
    """Find/search bar with next/previous navigation."""

    find_next = Signal(str, int)  # text, direction (1=next, -1=prev)
    search_text_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find...")
        self.search_input.textChanged.connect(self.search_text_changed.emit)
        self.search_input.returnPressed.connect(self.on_find_next)
        layout.addWidget(self.search_input)

        # Column selector
        self.column_combo = QComboBox()
        self.column_combo.addItem("All columns")
        layout.addWidget(self.column_combo)

        # Next button
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.on_find_next)
        layout.addWidget(self.btn_next)

        # Previous button
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.on_find_prev)
        layout.addWidget(self.btn_prev)

        # Close button
        self.btn_close = QPushButton("×")
        self.btn_close.setMaximumWidth(30)
        layout.addWidget(self.btn_close)

        self.setLayout(layout)

    def on_find_next(self):
        self.find_next.emit(self.search_input.text(), 1)

    def on_find_prev(self):
        self.find_next.emit(self.search_input.text(), -1)

    def update_columns(self, column_count: int, headers=None):
        """Update the column dropdown."""
        self.column_combo.clear()
        self.column_combo.addItem("All columns", -1)
        for i in range(column_count):
            if headers and i < len(headers):
                self.column_combo.addItem(f"Column {i}: {headers[i]}", i)
            else:
                self.column_combo.addItem(f"Column {i}", i)

    def get_search_column(self) -> int:
        """Get selected column index (-1 = all)."""
        return self.column_combo.currentData()

    def get_search_text(self) -> str:
        """Get search text."""
        return self.search_input.text()

    def clear(self):
        """Clear search field."""
        self.search_input.clear()
