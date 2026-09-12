@echo off
setlocal
cd /d "%~dp0"
title JAR Vietnamese Translator

if not exist "app.py" (
    echo [ERROR] Khong tim thay app.py trong thu muc:
    echo %CD%
    pause
    exit /b 1
)

if exist ".venv\Scripts\pythonw.exe" goto RUN

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto NOPYTHON
    set "PY=python"
)

echo ============================================
echo  JAR Vietnamese Translator - First Setup
echo ============================================
echo.
echo Dang tao moi truong Python...
%PY% -m venv .venv
if errorlevel 1 goto SETUPERROR

echo Dang cai dat thu vien can thiet...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto SETUPERROR

if exist "requirements.txt" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto SETUPERROR
)

:RUN
start "" ".venv\Scripts\pythonw.exe" "app.py"
exit /b 0

:NOPYTHON
echo.
echo [ERROR] PC chua co Python hoac Python chua duoc them vao PATH.
echo Hay cai Python 3.10 tro len, sau do double-click RUN_JAR_TRANSLATOR.bat lai.
echo.
pause
exit /b 1

:SETUPERROR
echo.
echo [ERROR] Khong the hoan tat cai dat tu dong.
echo Kiem tra ket noi Internet va Python, sau do chay lai file nay.
echo.
pause
exit /b 1
