@echo off
setlocal
cd /d "%~dp0"
title Build JAR Vietnamese Translator Portable

echo ===============================================
echo  JAR Vietnamese Translator - Portable EXE
echo ===============================================
echo.

if not exist "app.py" (
    echo [ERROR] Khong tim thay app.py.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" goto HAVEVENV

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto NOPYTHON
    set "PY=python"
)

echo [1/5] Tao moi truong Python...
%PY% -m venv .venv
if errorlevel 1 goto BUILDERROR

:HAVEVENV
echo [2/5] Cap nhat pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto BUILDERROR

echo [3/5] Cai dependencies...
if exist "requirements.txt" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto BUILDERROR
)

echo [4/5] Cai PyInstaller...
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto BUILDERROR

echo [5/5] Build portable EXE...
if exist "build" rmdir /s /q "build"
if exist "dist\JAR Vietnamese Translator" rmdir /s /q "dist\JAR Vietnamese Translator"

".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "JAR Vietnamese Translator" ^
    --collect-all PySide6 ^
    "app.py"

if errorlevel 1 goto BUILDERROR

echo.
echo ===============================================
echo BUILD THANH CONG
echo ===============================================
echo File chay:
echo %CD%\dist\JAR Vietnamese Translator\JAR Vietnamese Translator.exe
echo.
echo Thu muc "dist\JAR Vietnamese Translator" la ban Portable.
echo Co the copy nguyen thu muc nay sang PC Windows khac.
echo.
start "" "%CD%\dist\JAR Vietnamese Translator\JAR Vietnamese Translator.exe"
pause
exit /b 0

:NOPYTHON
echo.
echo [ERROR] Chua co Python 3.10+ tren may.
echo Cai Python, danh dau "Add Python to PATH",
echo sau do double-click BUILD_PORTABLE_EXE.bat lai.
echo.
pause
exit /b 1

:BUILDERROR
echo.
echo [ERROR] Build that bai.
echo Kiem tra Python va ket noi Internet roi chay lai.
echo.
pause
exit /b 1
