"""
Generates icon.png (multi-size) and icon.icns from icon.svg.
Run once: python3 assets/build_icon.py
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QImage, QPainter, QIcon, QPixmap
from PySide6.QtCore import Qt, QSize

app = QApplication.instance() or QApplication(sys.argv)

ASSETS = Path(__file__).parent
SVG = ASSETS / "icon.svg"

renderer = QSvgRenderer(str(SVG))

SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]

# ── Render each size to PNG ────────────────────────────────────────────────
png_dir = ASSETS / "icon.iconset"
png_dir.mkdir(exist_ok=True)

for size in SIZES:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    out = png_dir / f"icon_{size}x{size}.png"
    img.save(str(out))
    print(f"  {out.name}")

# macOS iconutil expects specific filenames
ICONSET_MAP = {
    "icon_16x16.png":    "icon_16x16.png",
    "icon_32x32.png":    "icon_16x16@2x.png",
    "icon_32x32.png":    "icon_32x32.png",
    "icon_64x64.png":    "icon_32x32@2x.png",
    "icon_128x128.png":  "icon_128x128.png",
    "icon_256x256.png":  "icon_128x128@2x.png",
    "icon_256x256.png":  "icon_256x256.png",
    "icon_512x512.png":  "icon_256x256@2x.png",
    "icon_512x512.png":  "icon_512x512.png",
    "icon_1024x1024.png":"icon_512x512@2x.png",
}

# Build a clean iconset directory with correct names
iconset = ASSETS / "Schichtplanung.iconset"
iconset.mkdir(exist_ok=True)
for src_name, dst_name in ICONSET_MAP.items():
    src = png_dir / src_name
    if src.exists():
        shutil.copy2(src, iconset / dst_name)

# ── Build .icns via iconutil (macOS only) ─────────────────────────────────
icns_out = ASSETS / "icon.icns"
result = subprocess.run(
    ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_out)],
    capture_output=True, text=True,
)
if result.returncode == 0:
    print(f"Created {icns_out}")
else:
    print(f"iconutil failed: {result.stderr}")

# ── Save a single 512px PNG for Qt window icon ────────────────────────────
shutil.copy2(png_dir / "icon_512x512.png", ASSETS / "icon.png")
print(f"Created {ASSETS / 'icon.png'}")
