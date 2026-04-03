@echo off
cd /d "%~dp0"
echo === Schichtplanung - Windows Build ===
echo.

REM --- 1. Python prüfen ---
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python nicht gefunden.
    echo Bitte Python von https://python.org installieren und "Add to PATH" anhaaken.
    pause
    exit /b 1
)

REM --- 2. Abhängigkeiten installieren ---
echo [1/4] Installiere Python-Pakete...
pip install --quiet PySide6 sqlalchemy ortools reportlab pyinstaller

REM --- 3. App bauen ---
echo [2/4] Baue App mit PyInstaller...
python -m PyInstaller ^
  --windowed ^
  --name "Schichtplanung" ^
  --collect-all ortools ^
  --collect-all PySide6 ^
  --collect-all reportlab ^
  --hidden-import sqlalchemy.dialects.sqlite ^
  --noconfirm ^
  main.py

REM --- 4. Inno Setup herunterladen falls nicht vorhanden ---
echo [3/4] Prüfe Inno Setup...
set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO% (
    echo     Inno Setup nicht gefunden, wird heruntergeladen...
    curl -L -o "%TEMP%\innosetup.exe" "https://jrsoftware.org/download.php/is.exe"
    echo     Installiere Inno Setup still...
    "%TEMP%\innosetup.exe" /VERYSILENT /NORESTART
)

REM --- 5. Installer bauen ---
echo [4/4] Erstelle Installer...
mkdir installer_output 2>nul
%INNO% installer.iss

echo.
echo === Fertig! ===
echo Installer liegt unter: installer_output\Schichtplanung_Setup.exe
echo Diese Datei an Endnutzer weitergeben.
echo.
pause
