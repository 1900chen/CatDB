@echo off
chcp 65001 >nul
echo ========================================
echo    豆包喵喵 便携版打包工具 (带图标)
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo [1/4] 检查并安装 PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    pip install pyinstaller
)

echo [2/4] 安装项目依赖...
pip install -r requirements.txt

echo [3/4] 开始打包 (包含图标)...
echo.

REM 使用 PyInstaller 打包
REM --onefile: 打包成单个 exe
REM --noconsole: 保留控制台以显示 IP 地址和提醒
REM --name: 指定输出文件名
REM --icon: 使用指定图标
REM --clean: 清理临时文件

pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "豆包喵喵" ^
    --icon "6-phone-cat_icon-icons.com_76682.ico" ^
    --clean ^
    server.py

echo.
echo [4/4] 打包完成！
echo.
echo ========================================
echo 📦 便携版位置: dist\豆包喵喵.exe
echo ========================================
echo.
echo 💡 使用方法：
echo    直接双击运行即可。
echo.
pause
