@echo off
setlocal
echo ============================================================
echo  IT Proposal Generator
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
echo Generating proposal (bundled HPC sample) -^> proposal.pdf + proposal.vsdx
echo.

python -m proposal_generator --out "%~dp0proposal.pdf" --vsdx "%~dp0proposal.vsdx" %*

echo.
echo Done! Open proposal.pdf
pause
