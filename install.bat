@echo off
chcp 65001 >nul 2>&1
title Voice Input Sync - Install

echo.
echo ========================================================
echo           Voice Input Sync - Install Dependencies
echo ========================================================
echo.

REM Check Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python first.
    echo         Download: https://www.python.org/downloads/
    goto :error
)
python --version
echo [OK] Python ready
echo.

REM Upgrade pip
echo [2/5] Upgrading pip...
python -m pip install --upgrade pip -q
echo [OK] pip updated
echo.

REM Install dependencies
echo [3/5] Installing aiohttp...
pip install aiohttp -q
if %errorlevel% neq 0 (
    echo [ERROR] aiohttp install failed
    goto :error
)
echo [OK] aiohttp installed

echo [4/5] Installing pyautogui, pyperclip...
pip install pyautogui pyperclip -q
if %errorlevel% neq 0 (
    echo [ERROR] pyautogui/pyperclip install failed
    goto :error
)
echo [OK] pyautogui, pyperclip installed

echo [5/5] Installing pynput...
pip install pynput -q
if %errorlevel% neq 0 (
    echo [ERROR] pynput install failed
    goto :error
)
echo [OK] pynput installed
echo.

REM Verify installation
echo --------------------------------------------------------
echo Verifying installed packages...
echo.
pip show aiohttp 2>nul | findstr "Name Version"
pip show pyautogui 2>nul | findstr "Name Version"
pip show pyperclip 2>nul | findstr "Name Version"
pip show pynput 2>nul | findstr "Name Version"
echo.

echo ========================================================
echo   [SUCCESS] All dependencies installed!
echo   
echo   Run: double-click start.bat to start the server
echo ========================================================
echo.
pause
exit /b 0

:error
echo.
echo ========================================================
echo   [ERROR] Installation failed
echo   
echo   Please check:
echo   1. Network connection
echo   2. Run as Administrator
echo   3. pip configuration
echo ========================================================
echo.
pause
exit /b 1
