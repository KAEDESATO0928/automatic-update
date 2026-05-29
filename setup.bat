@echo off
title So-net RPA Setup
cd /d "%~dp0"

echo ============================================
echo  So-net Auto Entry RPA - Setup
echo ============================================
echo.

REM Detect if running from a Temp folder (ZIP opened-not-extracted)
echo %~dp0 | findstr /I /C:"\\Temp\\" >nul
if not errorlevel 1 (
    echo [X] This setup.bat is running from a Temp folder.
    echo.
    echo This usually means the ZIP was OPENED without being extracted.
    echo.
    echo Please:
    echo   1. Close this window
    echo   2. Right-click the ZIP file
    echo   3. Choose "Extract All..." then click "Extract"
    echo   4. Open the extracted folder
    echo   5. Run setup.bat from there
    echo.
    pause
    exit /b 1
)
echo %~dp0 | findstr /I /C:"\\AppData\\Local\\Temp\\" >nul
if not errorlevel 1 (
    echo [X] Running from Temp. Please extract the ZIP properly first.
    pause
    exit /b 1
)

echo Install location: %~dp0
echo.

echo [1/2] Installing Firefox (a few minutes)...
python\python.exe -m playwright install firefox
if errorlevel 1 (
    echo [X] Firefox install failed.
    pause
    exit /b 1
)
echo     Done.
echo.

echo [2/2] Registering URL scheme (apclo-sonet://)...
set "BAT_PATH=%~dp0sonet-rpa.bat"

reg add "HKCU\Software\Classes\apclo-sonet" /ve /d "URL:apclo Sonet RPA Protocol" /f >nul
if errorlevel 1 ( echo [X] Registry write failed 1/3 & pause & exit /b 1 )

reg add "HKCU\Software\Classes\apclo-sonet" /v "URL Protocol" /t REG_SZ /d "" /f >nul
if errorlevel 1 ( echo [X] Registry write failed 2/3 & pause & exit /b 1 )

reg add "HKCU\Software\Classes\apclo-sonet\shell\open\command" /ve /d "\"%BAT_PATH%\" \"%%1\"" /f >nul
if errorlevel 1 ( echo [X] Registry write failed 3/3 & pause & exit /b 1 )

echo     Done.
echo.
echo     Verifying:
reg query "HKCU\Software\Classes\apclo-sonet\shell\open\command" /ve
echo.

echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo Open kintone, view a record, click the blue
echo "So-net RPA" button to trigger automation.
echo.
echo On first click, Windows asks which app to use.
echo Select "sonet-rpa", check "Always use this app",
echo then click "Open".
echo.
echo Press any key to close this window...
pause >nul