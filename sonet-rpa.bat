@echo off
REM apclo-sonet:// URLスキームから呼ばれるラッパー
REM 引数1に URL が渡される
cd /d "%~dp0"
python main.py "%~1"
