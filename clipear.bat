@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%GEMINI_API_KEY%"=="" (
  echo Falta la variable GEMINI_API_KEY. Mira el README.
  pause
  exit /b
)
:loop
set "LINK="
set "TRAMO="
set /p LINK=Pega el link del video (o escribe salir): 
if "%LINK%"=="" goto loop
if /i "%LINK%"=="salir" exit /b
set /p TRAMO=Tramo opcional, ej "--desde 2:14 --hasta 20:00" (Enter = video entero): 
py -3.13 clip.py "%LINK%" %TRAMO%
echo.
goto loop
