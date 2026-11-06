"""Tab widget for one CSV file with toolbar, table, and find bar."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt, Signal
from ..model import CsvSortFilterProxyModel
from .table_view import CsvTableView
from .find_bar import FindBar


class CsvTab(QWidget):
    """Tab for a single CSV file."""

    file_modified = Signal(str, bool)  # filepath, is_modified

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.proxy_model = CsvSortFilterProxyModel()
        self.init_ui()
        self.setup_toolbar_actions()

    def init_ui(self):
        """Build tab layout."""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar_layout = QHBoxLayout()

        # Delimiter selector
        toolbar_layout.addWidget(QLabel("Delimiter:"))
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([",", ";", "Tab", "|"])
        self.delimiter_combo.currentTextChanged.connect(self.on_delimiter_changed)
        toolbar_layout.addWidget(self.delimiter_combo)

        # Encoding selector
        toolbar_layout.addWidget(QLabel("Encoding:"))
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["UTF-8", "UTF-8 BOM", "Windows-1252", "Windows-1250"])
        self.encoding_combo.currentTextChanged.connect(self.on_encoding_changed)
        toolbar_layout.addWidget(self.encoding_combo)

        # Header toggle
        self.header_checkbox = QCheckBox("First row is header")
        self.header_checkbox.setChecked(True)
        self.header_checkbox.stateChanged.connect(self.on_header_toggle)
        toolbar_layout.addWidget(self.header_checkbox)

        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # Quick filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter...")
        self.filter_input.textChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_input)
        layout.addLayout(filter_layout)

        # Table view
        self.table_view = CsvTableView()
        self.table_view.setModel(self.proxy_model)
        layout.addWidget(self.table_view)

        # Find bar (hidden by default)
        self.find_bar = FindBar()
        self.find_bar.hide()
        self.find_bar.btn_close.clicked.connect(lambda: self.find_bar.hide())
        self.find_bar.find_next.connect(self.on_find)
        layout.addWidget(self.find_bar)

        self.setLayout(layout)

    def setup_toolbar_actions(self):
        """Connect toolbar actions."""
        pass  # Actions already connected in init_ui

    def on_delimiter_changed(self, text: str):
        """Update delimiter in model."""
        model = self.proxy_model.source_model()
        if text == "Tab":
            model.delimiter = "\t"
        else:
            model.delimiter = text
        model.set_modified(True)

    def on_encoding_changed(self, text: str):
        """Update encoding in model."""
        encoding_map = {
            "UTF-8": "utf-8",
            "UTF-8 BOM": "utf-8-sig",
            "Windows-1252": "windows-1252",
            "Windows-1250": "windows-1250",
        }
        model = self.proxy_model.source_model()
        model.encoding = encoding_map.get(text, "utf-8")
        model.set_modified(True)

    def on_header_toggle(self, state):
        """Toggle first-row-as-header mode."""
        model = self.proxy_model.source_model()
        model.set_has_header(state == Qt.Checked)
        self.find_bar.update_columns(model.columnCount(), model.header_row)

    def on_filter_changed(self, text: str):
        """Update filter in proxy model."""
        self.proxy_model.set_filter(text)

    def on_find(self, text: str, direction: int):
        """Find and select cells."""
        # TODO: Implement find/next/prev logic
        pass

    def show_find_bar(self):
        """Show the find bar."""
        self.find_bar.show()
        self.find_bar.search_input.setFocus()
        self.find_bar.search_input.selectAll()

    def get_model(self) -> CsvSortFilterProxyModel:
        """Get the model."""
        return self.proxy_model

    def set_file_modified(self, modified: bool):
        """Set file modified status."""
        self.file_modified.emit(self.filepath, modified)
