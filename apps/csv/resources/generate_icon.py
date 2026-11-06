"""Generate professional PPTX-style CSV icon."""
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow not installed. Using fallback: solid color icon.")
    sys.exit(0)

# Create PPTX-style CSV icon
size = 256
# Professional blue (like Excel)
primary_color = (26, 118, 188)  # #1A76BC - Professional blue
accent_color = (41, 184, 219)   # #29B8DB - Bright cyan accent
dark_bg = (20, 89, 143)         # Darker blue for depth
light_text = (255, 255, 255)    # White

img = Image.new("RGB", (size, size), primary_color)
draw = ImageDraw.Draw(img)

# Add subtle rounded gradient effect with darker edges
corner_radius = 30
for y in range(size):
    for x in range(size):
        dist_to_corner = min(
            abs(x - corner_radius),
            abs(y - corner_radius),
            abs(x - (size - corner_radius)),
            abs(y - (size - corner_radius))
        )
        if dist_to_corner < 0:
            alpha = max(0, min(255, 255 - (-dist_to_corner * 5)))

# Draw a document/spreadsheet shape (rounded rectangle with shadow)
doc_margin = 30
doc_x1, doc_y1 = doc_margin, doc_margin
doc_x2, doc_y2 = size - doc_margin, size - doc_margin

# Draw slight shadow
shadow_offset = 3
draw.rectangle(
    [(doc_x1 + shadow_offset, doc_y1 + shadow_offset),
     (doc_x2 + shadow_offset, doc_y2 + shadow_offset)],
    fill=(0, 0, 0, 30),
    outline=None
)

# Draw main document shape with white background
draw.rectangle(
    [(doc_x1, doc_y1), (doc_x2, doc_y2)],
    fill=light_text,
    outline=primary_color,
    width=3
)

# Draw a professional CSV table inside
table_margin = 15
table_x1 = doc_x1 + table_margin
table_y1 = doc_y1 + table_margin
table_x2 = doc_x2 - table_margin
table_y2 = doc_y2 - table_margin

# Create a 3x4 grid (header + 3 data rows, 4 columns)
rows = 4
cols = 4
col_width = (table_x2 - table_x1) / cols
row_height = (table_y2 - table_y1) / rows

# Draw grid lines
for row in range(rows + 1):
    y = table_y1 + row * row_height
    draw.line([(table_x1, y), (table_x2, y)], fill=primary_color, width=1)

for col in range(cols + 1):
    x = table_x1 + col * col_width
    draw.line([(x, table_y1), (x, table_y2)], fill=primary_color, width=1)

# Color the header row
header_y1 = table_y1
header_y2 = table_y1 + row_height
draw.rectangle(
    [(table_x1, header_y1), (table_x2, header_y2)],
    fill=primary_color
)

# Add colored data cells (accent color) to show data
data_colors = [
    (76, 175, 80),   # Green
    (156, 39, 176),  # Purple
    (255, 152, 0),   # Orange
    (244, 67, 54),   # Red
]

for row in range(1, 3):  # First 2 data rows
    for col in range(min(2, cols)):  # First 2 columns
        cell_x1 = table_x1 + col * col_width + 2
        cell_y1 = table_y1 + row * row_height + 2
        cell_x2 = cell_x1 + col_width - 4
        cell_y2 = cell_y1 + row_height - 4

        color = data_colors[(row + col) % len(data_colors)]
        draw.rectangle([cell_x1, cell_y1, cell_x2, cell_y2], fill=color)

# Add a small "CSV" or spreadsheet indicator
# Draw accent line at bottom to show it's modern
accent_bar_y = doc_y2 - 8
draw.rectangle(
    [(doc_x1, accent_bar_y), (doc_x2, doc_y2)],
    fill=accent_color
)

icon_path = Path(__file__).parent / "app.ico"
img.save(icon_path, format="ICO")
print(f"✓ Generated professional CSV icon: {icon_path}")
