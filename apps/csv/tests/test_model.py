"""Tests for CSV table model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.csv.model import CsvTableModel, col_letter


def test_col_letter():
    """Test column letter conversion."""
    assert col_letter(0) == "A"
    assert col_letter(25) == "Z"
    assert col_letter(26) == "AA"
    assert col_letter(27) == "AB"
    assert col_letter(51) == "AZ"
    assert col_letter(52) == "BA"


def test_model_data():
    """Test model data storage and retrieval."""
    model = CsvTableModel()

    rows = [
        ["Name", "Age", "City"],
        ["Alice", "30", "New York"],
        ["Bob", "25", "London"],
    ]

    model.set_data_from_rows(rows, "utf-8", ",", "\r\n", "/test.csv")

    assert model.rowCount() == 2  # Excluding header
    assert model.columnCount() == 3


def test_model_ragged_rows():
    """Test model with ragged rows."""
    model = CsvTableModel()

    rows = [
        ["A", "B", "C"],
        ["1", "2"],
        ["3", "4", "5", "6"],
    ]

    model.set_data_from_rows(rows, "utf-8", ",", "\r\n", "/test.csv")

    assert model.columnCount() == 4  # Max length


def test_model_edit():
    """Test model editing."""
    model = CsvTableModel()

    rows = [
        ["Name", "Age"],
        ["Alice", "30"],
    ]

    model.set_data_from_rows(rows, "utf-8", ",", "\r\n", "/test.csv")

    # Edit a cell
    index = model.index(0, 1)
    model.setData(index, "35")

    assert model.data(index) == "35"
    assert model.is_modified()


def test_model_header_toggle():
    """Test header toggle."""
    model = CsvTableModel()

    rows = [
        ["Name", "Age"],
        ["Alice", "30"],
        ["Bob", "25"],
    ]

    model.set_data_from_rows(rows, "utf-8", ",", "\r\n", "/test.csv")

    assert model.rowCount() == 2  # With header toggle on
    model.set_has_header(False)
    assert model.rowCount() == 3  # All rows
    model.set_has_header(True)
    assert model.rowCount() == 2  # Back to 2


if __name__ == "__main__":
    test_col_letter()
    print("✓ test_col_letter")

    test_model_data()
    print("✓ test_model_data")

    test_model_ragged_rows()
    print("✓ test_model_ragged_rows")

    test_model_edit()
    print("✓ test_model_edit")

    test_model_header_toggle()
    print("✓ test_model_header_toggle")

    print("\nAll tests passed!")
