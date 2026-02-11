@echo off
:: Check for admin rights
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :admin
) else (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:admin
title Auto Game Controller
echo ===================================
echo   Auto Game Controller
echo ===================================
echo.

:: Get script directory
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo [INFO] Running as Administrator
echo [INFO] Project directory: %SCRIPT_DIR%
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.8+
    pause
    exit /b 1
)

:: Run program
echo [INFO] Starting program...
python "%SCRIPT_DIR%\gui.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with error code: %errorlevel%
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Program exited
echo.
pause
