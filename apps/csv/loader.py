"""
CSV file loader with encoding/delimiter detection and background parsing.
"""
import csv
import io
import os
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, List
from PySide6.QtCore import QObject, QThread, Signal


class EncodingType(Enum):
    UTF8 = "utf-8"
    UTF8_BOM = "utf-8-sig"
    WINDOWS1252 = "windows-1252"
    WINDOWS1250 = "windows-1250"


CENTRAL_EU_CHARS = set("ąćęłńóśźżČĎŘŠŤŮŽăşşţţćčđĐĘęěőűąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


def detect_encoding(data: bytes) -> Tuple[EncodingType, bool]:
    """
    Detect encoding: BOM first, then UTF-8, then cp1250 vs cp1252 heuristic.
    Returns (encoding, is_valid).
    """
    # Check BOM
    if data.startswith(b"\xef\xbb\xbf"):
        return EncodingType.UTF8_BOM, True

    # Try UTF-8
    try:
        data.decode("utf-8")
        return EncodingType.UTF8, True
    except UnicodeDecodeError:
        pass

    # Heuristic: cp1250 vs cp1252 by counting Central-European chars
    try:
        cp1250_text = data.decode("windows-1250", errors="replace")
        cp1252_text = data.decode("windows-1252", errors="replace")

        cp1250_score = sum(1 for c in cp1250_text if c in CENTRAL_EU_CHARS)
        cp1252_score = sum(1 for c in cp1252_text if c in CENTRAL_EU_CHARS)

        if cp1250_score > cp1252_score:
            return EncodingType.WINDOWS1250, True
        else:
            return EncodingType.WINDOWS1252, True
    except Exception:
        return EncodingType.WINDOWS1252, False


def detect_delimiter(sample: str, delimiters: str = ",;\t|") -> Tuple[str, int]:
    """
    Use csv.Sniffer to detect delimiter. Falls back to count-based heuristic.
    Returns (delimiter, confidence).
    """
    try:
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample, delimiters=delimiters).delimiter
        return delimiter, 100
    except csv.Error:
        pass

    # Fallback: count each delimiter
    counts = {d: sample.count(d) for d in delimiters}
    # Assume delimiter appears on each row, weight by line count
    lines = sample.count("\n")
    if lines > 0:
        weighted = {d: counts[d] / lines for d in delimiters}
    else:
        weighted = counts

    best = max(weighted, key=weighted.get, default=",")
    return best, max(weighted.values()) if weighted else 0


def detect_line_terminator(data: bytes) -> str:
    """Detect line terminator: CRLF or LF."""
    if b"\r\n" in data:
        return "\r\n"
    elif b"\n" in data:
        return "\n"
    else:
        return "\r\n"  # Default for new files


class CsvLoaderWorker(QObject):
    """Background loader emitting progress and finished signals."""

    progress = Signal(int)  # percent
    finished = Signal(list, str, str, str, str)  # rows, encoding, delimiter, line_terminator, filepath
    error = Signal(str)  # error message

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        """Load CSV file in background."""
        try:
            filepath = Path(self.filepath)

            # Read file
            with open(filepath, "rb") as f:
                data = f.read()

            file_size = len(data)

            # Detect encoding
            encoding_type, _ = detect_encoding(data)
            encoding = encoding_type.value

            # Detect line terminator
            line_terminator = detect_line_terminator(data)

            # Decode
            text = data.decode(encoding, errors="replace")

            # Detect delimiter from first 64KB
            sample = text[:min(65536, len(text))]
            delimiter, _ = detect_delimiter(sample)

            # Parse CSV incrementally, emitting progress
            rows = []
            reader = csv.reader(io.StringIO(text), delimiter=delimiter, quoting=csv.QUOTE_ALL)

            # Count total lines for progress
            total_lines = text.count("\n") + 1

            for idx, row in enumerate(reader):
                rows.append(row)
                if idx % 1000 == 0:
                    progress = int((idx / max(total_lines, 1)) * 100)
                    self.progress.emit(min(progress, 99))

            self.progress.emit(100)
            self.finished.emit(rows, encoding, delimiter, line_terminator, str(filepath.absolute()))

        except Exception as e:
            self.error.emit(f"Failed to load {self.filepath}: {str(e)}")


def load_csv_async(filepath: str) -> Tuple[QThread, CsvLoaderWorker]:
    """
    Create and start a background loader thread.
    Returns (thread, worker) so caller can connect signals.
    """
    thread = QThread()
    worker = CsvLoaderWorker(filepath)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    thread.start()
    return thread, worker


def save_csv(
    filepath: str,
    rows: List[List[str]],
    encoding: str = "utf-8",
    delimiter: str = ",",
    line_terminator: str = "\r\n",
) -> bool:
    """
    Save rows to CSV file with specified encoding, delimiter, and line terminator.
    Uses atomic write (temp file + replace) to avoid data loss.
    Returns True on success.
    """
    try:
        temp_filepath = str(Path(filepath).with_stem(Path(filepath).stem + ".tmp"))

        with open(temp_filepath, "w", encoding=encoding, newline="") as f:
            writer = csv.writer(f, delimiter=delimiter, lineterminator=line_terminator)
            writer.writerows(rows)

        # Atomic replace
        os.replace(temp_filepath, filepath)
        return True
    except UnicodeEncodeError:
        # Fallback to UTF-8 if encoding fails
        if encoding != "utf-8":
            return save_csv(filepath, rows, "utf-8", delimiter, line_terminator)
        raise
    except Exception as e:
        print(f"Failed to save {filepath}: {str(e)}")
        return False
