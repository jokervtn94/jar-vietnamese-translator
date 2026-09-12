@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Keo-tha file PATCH.zip vao APPLY_PATCH.bat
    echo hoac chay: APPLY_PATCH.bat path\to\PATCH.zip
    pause
    exit /b 1
)

if exist "runtime\python\python.exe" (
    "runtime\python\python.exe" apply_patch.py "%~1"
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" apply_patch.py "%~1"
) else (
    py apply_patch.py "%~1"
)

if errorlevel 1 (
    echo.
    echo [ERROR] Patch that bai. File cu da duoc rollback neu can.
) else (
    echo.
    echo Patch thanh cong. Khoi dong lai app.
)
pause
