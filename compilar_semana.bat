@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === VIDEO LARGO DE LA SEMANA ===
py -3.13 clip.py --compilar 7
pause
