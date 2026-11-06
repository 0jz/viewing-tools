"""Generate sample CSV files for testing."""
import csv
from pathlib import Path


def gen_semicolon():
    """Generate semicolon-delimited CSV."""
    with open(Path(__file__).parent / "semicolon.csv", "w", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Name", "Age", "City"])
        writer.writerow(["Alice", "30", "New York"])
        writer.writerow(["Bob", "25", "London"])
        writer.writerow(["Charlie", "35", "Paris"])


def gen_utf8_bom():
    """Generate UTF-8 with BOM."""
    with open(Path(__file__).parent / "utf8_bom.csv", "w", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow(["Product", "Price", "Stock"])
        writer.writerow(["Apple", "1.50", "100"])
        writer.writerow(["Banana", "0.75", "150"])
        writer.writerow(["Cherry", "2.00", "50"])


def gen_quoted_newlines():
    """Generate CSV with quoted fields containing newlines."""
    with open(Path(__file__).parent / "quoted_newlines.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["ID", "Description", "Notes"])
        writer.writerow(["1", "Product A", "High quality\nRecommended"])
        writer.writerow(["2", "Product B", "Contains tabs:\there"])
        writer.writerow(["3", 'Product "C"', "Quoted value"])


def gen_cp1250():
    """Generate Windows-1250 (Central European) encoded CSV."""
    with open(Path(__file__).parent / "cp1250.csv", "w", encoding="windows-1250") as f:
        f.write("Nazwa,Wiek,Miasto\n")
        f.write("Ąlicja,30,Kraków\n")
        f.write("Boguslav,25,Warszawa\n")
        f.write("Ćezary,35,Łódź\n")


def gen_big_file(rows=500000):
    """Generate large CSV file."""
    with open(Path(__file__).parent / f"big_{rows}.csv", "w", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow(["ID", "Name", "Value", "Status", "Notes"])
        for i in range(rows):
            writer.writerow([
                str(i),
                f"Item_{i}",
                str(i * 1.5),
                "Active" if i % 2 == 0 else "Inactive",
                f"Generated row {i}"
            ])


if __name__ == "__main__":
    print("Generating sample CSV files...")
    gen_semicolon()
    print("✓ semicolon.csv")

    gen_utf8_bom()
    print("✓ utf8_bom.csv")

    gen_quoted_newlines()
    print("✓ quoted_newlines.csv")

    gen_cp1250()
    print("✓ cp1250.csv")

    gen_big_file(500000)
    print("✓ big_500000.csv")

    print("Done!")
