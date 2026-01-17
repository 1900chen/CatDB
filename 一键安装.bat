@echo off
chcp 65001 >nul 2>&1
title 语音输入同步工具 - 一键安装
color 0B

echo.
echo ========================================================
echo        语音输入同步工具 - 一键完整安装
echo ========================================================
echo.
echo 此脚本将自动完成以下操作：
echo   1️⃣ 检查并安装 Python
echo   2️⃣ 安装程序依赖包
echo.
echo 请确保：
echo   ✓ 已连接网络
echo   ✓ 已关闭杀毒软件（避免误报）
echo.
pause
echo.

REM ==================================================
REM 步骤 1: 检查/安装 Python
REM ==================================================
echo.
echo ========================================================
echo   步骤 1/2: 检查 Python
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Python 已安装
    python --version
    goto :install_deps
)

echo ❌ Python 未安装，开始安装...
echo.

REM 检查 winget
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ⚠️  无法使用 winget 自动安装
    echo.
    echo 请手动安装 Python：
    echo   1. 访问 https://www.python.org/downloads/
    echo   2. 下载并安装（务必勾选 "Add Python to PATH"）
    echo   3. 重新运行此脚本
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo 使用 winget 安装 Python 3.12...
echo （这可能需要几分钟，请耐心等待）
echo.

winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements

if %errorlevel% neq 0 (
    echo.
    echo ❌ 自动安装失败
    echo.
    echo 请手动安装 Python：
    echo   1. 访问 https://www.python.org/downloads/
    echo   2. 下载并安装（务必勾选 "Add Python to PATH"）
    echo   3. 重新运行此脚本
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo ✅ Python 安装完成
echo.
echo ⚠️  重要：需要刷新环境变量
echo    请 **关闭此窗口** 并重新运行此脚本
echo.
pause
exit /b 0

REM ==================================================
REM 步骤 2: 安装依赖包
REM ==================================================
:install_deps
echo.
echo ========================================================
echo   步骤 2/2: 安装程序依赖
echo ========================================================
echo.

echo [1/4] 升级 pip...
python -m pip install --upgrade pip -q
if %errorlevel% neq 0 (
    echo ❌ pip 升级失败
    goto :error
)
echo ✅ pip 已升级

echo.
echo [2/4] 安装 aiohttp...
pip install aiohttp -q
if %errorlevel% neq 0 (
    echo ❌ aiohttp 安装失败
    goto :error
)
echo ✅ aiohttp 已安装

echo.
echo [3/4] 安装 pyautogui, pyperclip...
pip install pyautogui pyperclip -q
if %errorlevel% neq 0 (
    echo ❌ pyautogui/pyperclip 安装失败
    goto :error
)
echo ✅ pyautogui, pyperclip 已安装

echo.
echo [4/4] 安装 pynput...
pip install pynput -q
if %errorlevel% neq 0 (
    echo ❌ pynput 安装失败
    goto :error
)
echo ✅ pynput 已安装

echo.
echo ========================================================
echo   🎉 所有组件安装成功！
echo.
echo   下一步：双击运行 start.bat 启动服务
echo ========================================================
echo.
pause
exit /b 0

:error
echo.
echo ========================================================
echo   ❌ 安装失败
echo.
echo   请检查：
echo     1. 网络连接是否正常
echo     2. 是否以管理员身份运行
echo     3. 防火墙/杀毒软件是否拦截
echo.
echo   如果问题持续，请分步运行：
echo     1. install_python.bat
echo     2. install.bat
echo ========================================================
echo.
pause
exit /b 1
