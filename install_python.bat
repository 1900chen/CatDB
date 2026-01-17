@echo off
chcp 65001 >nul 2>&1
title Python 自动安装工具
color 0A

echo.
echo ========================================================
echo            Python 自动安装工具
echo ========================================================
echo.

REM 检查 Python 是否已安装
echo [1/3] 检查 Python 安装状态...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ✅ Python 已安装！
    python --version
    echo.
    echo ========================================================
    echo   无需安装，可以直接运行 install.bat
    echo ========================================================
    echo.
    pause
    exit /b 0
)

echo ❌ 未检测到 Python
echo.

REM 检查 winget 是否可用
echo [2/3] 检查 winget 包管理器...
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ winget 不可用
    goto :manual_download
)

echo ✅ winget 可用
winget --version
echo.

REM 使用 winget 安装 Python
echo [3/3] 正在使用 winget 安装 Python...
echo.
echo 📦 安装命令: winget install Python.Python.3.12 --silent
echo.
echo ⚠️  注意：安装过程可能需要几分钟，请耐心等待...
echo.

winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements

if %errorlevel% equ 0 (
    echo.
    echo ✅ Python 安装成功！
    echo.
    echo ⚠️  重要提示：
    echo    1. 请 **关闭并重新打开** 此命令行窗口
    echo    2. 然后运行 install.bat 安装其他依赖
    echo.
    echo ========================================================
    echo   安装成功！请按任意键退出，然后重新打开窗口
    echo ========================================================
    pause
    exit /b 0
) else (
    echo.
    echo ⚠️  winget 安装失败，尝试手动下载方式...
    echo.
    goto :manual_download
)

:manual_download
echo.
echo ========================================================
echo   需要手动安装 Python
echo ========================================================
echo.
echo 请按照以下步骤操作：
echo.
echo 1️⃣ 打开浏览器，访问 Python 官网：
echo    https://www.python.org/downloads/
echo.
echo 2️⃣ 下载最新版本的 Python（建议 3.9 或更高版本）
echo.
echo 3️⃣ 运行下载的安装程序时，⚠️ **务必勾选**：
echo    ☑️ "Add Python to PATH"
echo    ☑️ "Install for all users"（如果有此选项）
echo.
echo 4️⃣ 安装完成后，重新运行此批处理文件验证安装
echo.
echo ========================================================
echo.
echo 是否现在打开 Python 下载页面？(Y/N)
set /p choice=请输入选择: 

if /i "%choice%"=="Y" (
    start https://www.python.org/downloads/
    echo.
    echo 浏览器已打开下载页面
    echo 安装完成后请重新运行此文件
) else (
    echo.
    echo 请记住手动访问: https://www.python.org/downloads/
)

echo.
pause
exit /b 1
