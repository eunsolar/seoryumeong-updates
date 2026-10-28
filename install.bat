@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version
if errorlevel 1 (echo Python 3 is required. Visit python.org & pause & exit /b 1)
%PY% -m pip install --upgrade pymupdf pillow pytesseract xlsxwriter
if errorlevel 1 (echo Dependency installation failed. & pause & exit /b 1)
echo Dependencies installed.
pause
