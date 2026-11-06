"""Tests for CSV loader."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.csv.loader import detect_encoding, detect_delimiter, EncodingType


def test_detect_encoding_utf8():
    """Test UTF-8 detection."""
    data = "Hello,World\nAlice,30\n".encode("utf-8")
    encoding, _ = detect_encoding(data)
    assert encoding == EncodingType.UTF8


def test_detect_encoding_utf8_bom():
    """Test UTF-8 BOM detection."""
    data = "Hello,World\nAlice,30\n".encode("utf-8-sig")
    encoding, _ = detect_encoding(data)
    assert encoding == EncodingType.UTF8_BOM


def test_detect_delimiter_comma():
    """Test comma delimiter detection."""
    sample = "Name,Age,City\nAlice,30,New York\n"
    delim, conf = detect_delimiter(sample)
    assert delim == ","


def test_detect_delimiter_semicolon():
    """Test semicolon delimiter detection."""
    sample = "Name;Age;City\nAlice;30;Paris\n"
    delim, conf = detect_delimiter(sample)
    assert delim == ";"


def test_detect_delimiter_tab():
    """Test tab delimiter detection."""
    sample = "Name\tAge\tCity\nAlice\t30\tLondon\n"
    delim, conf = detect_delimiter(sample)
    assert delim == "\t"


if __name__ == "__main__":
    test_detect_encoding_utf8()
    print("✓ test_detect_encoding_utf8")

    test_detect_encoding_utf8_bom()
    print("✓ test_detect_encoding_utf8_bom")

    test_detect_delimiter_comma()
    print("✓ test_detect_delimiter_comma")

    test_detect_delimiter_semicolon()
    print("✓ test_detect_delimiter_semicolon")

    test_detect_delimiter_tab()
    print("✓ test_detect_delimiter_tab")

    print("\nAll tests passed!")
