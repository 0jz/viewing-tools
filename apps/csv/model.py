"""
CSV table model with sorting, filtering, and editing support.
"""
from typing import List, Optional
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Signal
from PySide6.QtGui import QColor


def col_letter(col: int) -> str:
    """Convert 0-based column index to Excel-style letter(s): 0→A, 25→Z, 26→AA."""
    result = ""
    col += 1
    while col > 0:
        col -= 1
        result = chr(65 + col % 26) + result
        col //= 26
    return result


class CsvTableModel(QAbstractTableModel):
    """
    Custom table model for CSV data with support for ragged rows,
    editing, sorting, filtering, and header toggle.
    """

    modifiedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: List[List[str]] = []
        self.encoding = "utf-8"
        self.delimiter = ","
        self.line_terminator = "\r\n"
        self.filepath = ""
        self.has_header = True
        self._modified = False
        self.header_row: Optional[List[str]] = None

    def set_modified(self, modified: bool):
        """Mark model as modified and emit signal."""
        if modified != self._modified:
            self._modified = modified
            self.modifiedChanged.emit(modified)

    def is_modified(self) -> bool:
        return self._modified

    def set_data_from_rows(
        self,
        rows: List[List[str]],
        encoding: str,
        delimiter: str,
        line_terminator: str,
        filepath: str,
    ):
        """Set model data from loaded rows."""
        self.beginResetModel()
        self.rows = rows
        self.encoding = encoding
        self.delimiter = delimiter
        self.line_terminator = line_terminator
        self.filepath = filepath
        self._modified = False
        self._update_header()
        self.endResetModel()

    def _update_header(self):
        """Extract header row if has_header is True."""
        if self.has_header and self.rows:
            self.header_row = self.rows[0]
        else:
            self.header_row = None

    def set_has_header(self, has_header: bool):
        """Toggle first-row-as-header mode."""
        self.beginResetModel()
        self.has_header = has_header
        self._update_header()
        self.endResetModel()

    def data_rows(self) -> List[List[str]]:
        """Return data rows (excluding header if has_header is True)."""
        if self.has_header and self.rows:
            return self.rows[1:]
        return self.rows

    def all_rows(self) -> List[List[str]]:
        """Return all rows including header."""
        return self.rows

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.data_rows())

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        if not self.rows:
            return 0
        return max(len(row) for row in self.rows) if self.rows else 0

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if self.has_header and self.rows:
            data_row = self.rows[row + 1]
        else:
            data_row = self.rows[row]

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col < len(data_row):
                return data_row[col]
            return ""

        return None

    def setData(self, index: QModelIndex, value, role=Qt.EditRole) -> bool:
        if not index.isValid():
            return False

        row = index.row()
        col = index.column()

        if self.has_header and self.rows:
            data_row = self.rows[row + 1]
        else:
            data_row = self.rows[row]

        # Pad row if necessary
        while len(data_row) <= col:
            data_row.append("")

        data_row[col] = str(value)
        self.dataChanged.emit(index, index)
        self.set_modified(True)
        return True

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            letter = col_letter(section)
            if self.has_header and self.header_row and section < len(self.header_row):
                return f"{letter} · {self.header_row[section]}"
            return letter
        elif orientation == Qt.Vertical:
            return str(section + 1)

        return None

    def flags(self, index: QModelIndex):
        return super().flags(index) | Qt.ItemIsEditable

    def insertRows(self, row: int, count: int, parent=QModelIndex()) -> bool:
        self.beginInsertRows(parent, row, row + count - 1)
        data_rows = self.data_rows()
        for i in range(count):
            if self.has_header:
                self.rows.insert(row + 1 + i, [])
            else:
                self.rows.insert(row + i, [])
        self.endInsertRows()
        self.set_modified(True)
        return True

    def removeRows(self, row: int, count: int, parent=QModelIndex()) -> bool:
        self.beginRemoveRows(parent, row, row + count - 1)
        for i in range(count):
            if self.has_header:
                del self.rows[row + 1]
            else:
                del self.rows[row]
        self.endRemoveRows()
        self.set_modified(True)
        return True

    def insertColumns(self, column: int, count: int, parent=QModelIndex()) -> bool:
        self.beginInsertColumns(parent, column, column + count - 1)
        for row in self.rows:
            for i in range(count):
                row.insert(column, "")
        self.endInsertColumns()
        self.set_modified(True)
        return True

    def removeColumns(self, column: int, count: int, parent=QModelIndex()) -> bool:
        self.beginRemoveColumns(parent, column, column + count - 1)
        for row in self.rows:
            for i in range(count):
                if column < len(row):
                    del row[column]
        self.endRemoveColumns()
        self.set_modified(True)
        return True


class CsvSortFilterProxyModel(QSortFilterProxyModel):
    """
    Sort/filter proxy with numeric-aware sorting.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSourceModel(CsvTableModel(self))
        self.filter_text = ""
        self.filter_column = -1  # -1 = all columns

    def lessThan(self, left_index: QModelIndex, right_index: QModelIndex) -> bool:
        """Numeric-aware less-than for sorting."""
        left_data = self.sourceModel().data(left_index, Qt.DisplayRole)
        right_data = self.sourceModel().data(right_index, Qt.DisplayRole)

        if left_data is None:
            left_data = ""
        if right_data is None:
            right_data = ""

        # Try numeric comparison
        try:
            left_num = float(str(left_data).replace(",", "."))
            right_num = float(str(right_data).replace(",", "."))
            return left_num < right_num
        except (ValueError, TypeError):
            pass

        # Fallback: text comparison
        return str(left_data).lower() < str(right_data).lower()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Case-insensitive substring filter."""
        if not self.filter_text:
            return True

        source_model = self.sourceModel()

        if self.filter_column >= 0:
            # Filter specific column
            index = source_model.index(source_row, self.filter_column, source_parent)
            data = source_model.data(index, Qt.DisplayRole)
            return self.filter_text.lower() in str(data).lower()
        else:
            # Filter all columns
            col_count = source_model.columnCount(source_parent)
            for col in range(col_count):
                index = source_model.index(source_row, col, source_parent)
                data = source_model.data(index, Qt.DisplayRole)
                if self.filter_text.lower() in str(data).lower():
                    return True
            return False

    def set_filter(self, text: str, column: int = -1):
        """Set filter text and column. -1 = all columns."""
        self.filter_text = text
        self.filter_column = column
        self.invalidateFilter()

    def source_model(self) -> CsvTableModel:
        return self.sourceModel()
