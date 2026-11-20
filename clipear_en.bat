@echo off
chcp 65001 >nul
cd /d "%~dp0"
set IDIOMA=en
echo === CANAL EN INGLES ===
:loop
set "LINK="
set /p LINK=Pega el link del video (o escribe salir): 
if "%LINK%"=="" goto loop
if /i "%LINK%"=="salir" exit /b
py -3.13 clip.py "%LINK%"
echo.
goto loop
