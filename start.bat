@echo off
echo ========================================
echo  ShareaSpot - Starting...
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: Python not found!
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b
)

echo.
echo [2/3] Installing dependencies...
python -m pip install fastapi uvicorn sqlalchemy python-multipart pillow aiofiles
if errorlevel 1 (
    echo.
    echo ERROR: Dependency install failed. See error above.
    pause
    exit /b
)

echo.
echo [3/3] Starting ShareaSpot server...
echo.
echo ========================================
echo  App is running at: http://localhost:8000
echo  Open that address in your browser.
echo  Keep this window open while using app.
echo  Press Ctrl+C to stop.
echo ========================================
echo.

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

echo.
echo Server stopped.
pause
