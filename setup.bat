@echo off
chcp 65001 >nul
title So-net 自動申込 RPA セットアップ
cd /d "%~dp0"

echo ============================================
echo  So-net 自動申込 RPA セットアップ
echo ============================================
echo.

REM ---- 1. Python 確認 ----
where python >nul 2>&1
if errorlevel 1 (
    echo [!] Python が見つかりませんでした。
    echo.
    echo Microsoft Store を開きます。「入手」ボタンで
    echo Python 3.13 をインストール後、もう一度この
    echo setup.bat をダブルクリックしてください。
    echo.
    pause
    start ms-windows-store://pdp?productid=9NCVDN91XZQP
    exit /b 1
)

echo [1/3] Python パッケージ インストール中...
python -m pip install --upgrade pip --quiet
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [X] パッケージインストールに失敗しました。
    pause
    exit /b 1
)
echo     完了。
echo.

echo [2/3] Firefox インストール中... (数分かかります)
python -m playwright install firefox
if errorlevel 1 (
    echo [X] Firefox インストールに失敗しました。
    pause
    exit /b 1
)
echo     完了。
echo.

echo [3/3] URLスキーム (apclo-sonet://) 登録中...
set "BAT_PATH=%~dp0sonet-rpa.bat"
set "BAT_PATH_ESC=%BAT_PATH:\=\\%"

(
echo REGEDIT4
echo.
echo [HKEY_CURRENT_USER\Software\Classes\apclo-sonet]
echo @="URL:apclo Sonet RPA Protocol"
echo "URL Protocol"=""
echo.
echo [HKEY_CURRENT_USER\Software\Classes\apclo-sonet\shell]
echo.
echo [HKEY_CURRENT_USER\Software\Classes\apclo-sonet\shell\open]
echo.
echo [HKEY_CURRENT_USER\Software\Classes\apclo-sonet\shell\open\command]
echo @="\"%BAT_PATH_ESC%\" \"%%1\""
) > "%TEMP%\apclo-sonet-register.reg"

reg import "%TEMP%\apclo-sonet-register.reg" >nul 2>&1
del "%TEMP%\apclo-sonet-register.reg"
echo     完了。
echo.

echo ============================================
echo  セットアップ完了！
echo ============================================
echo.
echo kintone でレコードを開き、青いボタンを押すと
echo Firefox が起動して自動入力が始まります。
echo.
echo 初回のみ Windows から「このリンクで何を開く？」と
echo 聞かれます。「sonet-rpa」を選び「常に使う」に
echo チェックして「開く」を押してください。
echo.
pause
