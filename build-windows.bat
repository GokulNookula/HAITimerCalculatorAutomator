@echo off
setlocal
cd /d "%~dp0"
python build.py
if errorlevel 1 (
    echo.
    echo Build failed. Check the error above.
    pause
    exit /b 1
)
echo.
echo Build finished. Your executable is inside the dist folder.
pause
