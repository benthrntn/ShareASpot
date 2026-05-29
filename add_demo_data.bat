@echo off
echo ========================================
echo  ShareaSpot - Adding Demo Data
echo ========================================
echo.
cd /d "%~dp0backend"
python seed_data.py
echo.
pause
