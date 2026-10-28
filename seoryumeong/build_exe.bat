@echo off
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller pymupdf pillow pytesseract xlsxwriter
if errorlevel 1 (echo Failed to install build dependencies. & pause & exit /b 1)
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name Seoryumeong --icon dog.ico --add-data "dog.ico;." --add-data "version.json;." --add-data "updater.py;." --collect-all fitz --collect-all pytesseract app.py
if errorlevel 1 (echo Build failed. & pause & exit /b 1)
echo EXE created at dist\Seoryumeong.exe
pause
