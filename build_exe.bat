@echo off
setlocal enabledelayedexpansion

REM -----------------------------
REM Build settings
REM -----------------------------
set "APP_EXE_NAME=DeadByDaylightPerkShuffle"
set "ICON_FILE=app_icon.ico"
set "MAIN_FILE=main.py"

REM -----------------------------
REM Go to this script's folder
REM -----------------------------
cd /d "%~dp0"

REM -----------------------------
REM Make sure dependencies exist
REM -----------------------------
py -m pip install --upgrade pip >nul
py -m pip install pyinstaller pillow

REM -----------------------------
REM Clean old builds
REM -----------------------------
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist "%APP_EXE_NAME%.spec" del /q "%APP_EXE_NAME%.spec"

REM -----------------------------
REM Build with PyInstaller
REM -----------------------------
py -m PyInstaller --noconsole --onefile ^
  --name "%APP_EXE_NAME%" ^
  --icon "%ICON_FILE%" ^
  --add-data "perks.json;." ^
  --add-data "icons;icons" ^
  "%MAIN_FILE%"

REM -----------------------------
REM Done
REM -----------------------------
echo.
echo Build complete!
echo Output: "%cd%\dist\%APP_EXE_NAME%.exe"
pause
endlocal
