@echo off
setlocal
echo ============================================================
echo  HPC User Forum Sync
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause & exit /b 1
)

echo Installing/updating dependencies...
pip install -r "%~dp0requirements.txt" --quiet

echo.
echo Downloading attendee list files (PDF + XLS, last 2 years) to: %~dp0pdfs\
echo.

python "%~dp0crawl_hpcuserforum.py" --download --attendee-list --years 2 --output "%~dp0pdfs"

echo.
echo Done! Check pdfs\ for results.
pause
