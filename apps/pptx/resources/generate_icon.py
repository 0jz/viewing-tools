"""Generate resources/app.ico (a slide on an orange tile)."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=44, fill=(210, 71, 38))
d.rounded_rectangle([44, 66, S - 44, S - 78], radius=10, fill=(255, 255, 255))
d.rectangle([66, 92, 150, 104], fill=(210, 71, 38))
d.rectangle([66, 120, 190, 130], fill=(190, 195, 205))
d.rectangle([66, 142, 170, 152], fill=(190, 195, 205))
d.polygon([(S // 2 - 22, S - 70), (S // 2 + 22, S - 70), (S // 2, S - 46)], fill=(255, 255, 255))
out = Path(__file__).parent / "app.ico"
img.save(out, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", out)
