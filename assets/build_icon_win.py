"""
Generates icon.ico (Windows) from the rendered PNGs.
Run on Windows: python assets/build_icon_win.py
Requires: pip install pillow
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow nicht installiert: pip install pillow")
    sys.exit(1)

ASSETS = Path(__file__).parent
ICONSET = ASSETS / "icon.iconset"

sizes = [16, 32, 48, 64, 128, 256]
images = []
for s in sizes:
    p = ICONSET / f"icon_{s}x{s}.png"
    if p.exists():
        images.append(Image.open(p).convert("RGBA"))

out = ASSETS / "icon.ico"
images[0].save(
    out,
    format="ICO",
    sizes=[(img.width, img.height) for img in images],
    append_images=images[1:],
)
print(f"Erstellt: {out}")
