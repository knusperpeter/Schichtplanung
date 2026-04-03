#!/bin/bash
# Erstellt Schichtplanung.app im dist/ Verzeichnis
# Danach: dist/Schichtplanung.app auf Desktop oder in /Applications ziehen

set -e
cd "$(dirname "$0")"

echo "=== Schichtplanung – Build ==="

python3.12 -m PyInstaller \
  --windowed \
  --name "Schichtplanung" \
  --collect-all ortools \
  --collect-all PySide6 \
  --collect-all reportlab \
  --hidden-import sqlalchemy.dialects.sqlite \
  --noconfirm \
  main.py

echo ""
echo "Fertig! App liegt unter: dist/Schichtplanung.app"
echo ""
echo "Auf Desktop kopieren:"
echo "  cp -r dist/Schichtplanung.app ~/Desktop/"
