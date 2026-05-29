@echo off
cd /d "%~dp0"
if exist "python\python.exe" (
    python\python.exe main.py "%~1"
) else (
    python main.py "%~1"
)
if errorlevel 1 (
    echo.
    echo ====================================
    echo  Error - press any key to close
    pause
)