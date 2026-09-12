@echo off
setlocal
cd /d "%~dp0"
title Build JAR Vietnamese Translator Modular Portable

if not exist "launcher.py" (
    echo [ERROR] Khong tim thay launcher.py.
    pause
    exit /b 1
)

where py >nul 2>nul && (set "PY=py") || (set "PY=python")
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if errorlevel 1 goto BUILDERROR

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto BUILDERROR

if exist "build" rmdir /s /q "build"
if exist "dist\JAR Vietnamese Translator" rmdir /s /q "dist\JAR Vietnamese Translator"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean JAR_Translator.spec
if errorlevel 1 goto BUILDERROR

xcopy /E /I /Y "app" "dist\JAR Vietnamese Translator\app" >nul
xcopy /E /I /Y "config" "dist\JAR Vietnamese Translator\config" >nul
if exist "assets" xcopy /E /I /Y "assets" "dist\JAR Vietnamese Translator\assets" >nul
if not exist "dist\JAR Vietnamese Translator\updates" mkdir "dist\JAR Vietnamese Translator\updates"
if not exist "dist\JAR Vietnamese Translator\logs" mkdir "dist\JAR Vietnamese Translator\logs"

echo.
echo ===============================================
echo BUILD MODULAR THANH CONG
echo ===============================================
echo Runtime: dist\JAR Vietnamese Translator\JAR Vietnamese Translator.exe
echo Code:    dist\JAR Vietnamese Translator\app\
echo Config:  dist\JAR Vietnamese Translator\config\
echo.
echo Tu lan sau, neu chi sua app\ hoac theme thi KHONG can build lai runtime.
pause
exit /b 0

:BUILDERROR
echo [ERROR] Build that bai.
pause
exit /b 1
