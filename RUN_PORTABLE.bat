@echo off
setlocal
cd /d "%~dp0"
if exist "dist\JAR_Translator\JAR_Translator.exe" (
    start "" "dist\JAR_Translator\JAR_Translator.exe"
    exit /b 0
)
echo Chua tim thay ban Portable.
echo Hay double-click BUILD_PORTABLE_EXE.bat truoc.
pause
