@echo off
cd /d "%~dp0"
python main.py "%~1"
if errorlevel 1 (
    echo.
    echo ====================================
    echo  Error - press any key to close
    pause
)
