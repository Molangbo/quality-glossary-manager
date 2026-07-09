@echo off
chcp 65001 >nul
cd /d "%~dp0"
python src\web_app.py
pause
