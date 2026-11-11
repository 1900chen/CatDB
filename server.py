#!/usr/bin/env python3
"""
手机语音输入 → 电脑实时上屏（豆包喵喵·图形界面版）
- 依赖自动安装（国内镜像优先）
- Windows 无控制台启动（pythonw 重启）
- Tkinter GUI：二维码 + URL + 运行日志
- 窗口尺寸：屏幕 1/2 宽 × 2/3 高
- 上屏策略：新增字立即发送；删除/替换走 200ms 兜底合并
- backspace 加速

"""

import sys
import os
import queue
import subprocess
import importlib.util
import time

# ============== 依赖自动安装 ==============
PIP_MIRRORS = [
    ('清华', 'https://pypi.tuna.tsinghua.edu.cn/simple'),
    ('阿里', 'https://mirrors.aliyun.com/pypi/simple/'),
    ('腾讯', 'https://mirrors.cloud.tencent.com/pypi/simple/'),
    ('中科大', 'https://pypi.mirrors.ustc.edu.cn/simple/'),
]

_dep_logs = []


def _safe_print(msg):
    _dep_logs.append(msg)
    try:
        if sys.stdout is not None and hasattr(sys.stdout, 'write'):
            sys.stdout.write(msg + '\n')
            sys.stdout.flush()
    except Exception:
        pass


def _pip_install(packages, index_url=None):
    cmd = [sys.executable, '-m', 'pip', 'install', '--quiet',
           '--disable-pip-version-check']
    if index_url:
        cmd += ['-i', index_url]
    cmd += packages
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return True, ''
        return False, (r.stderr or r.stdout or '').strip()
    except Exception as e:
        return False, str(e)


def ensure_dependencies():
    required = [
        ('aiohttp',   'aiohttp'),
        ('pyautogui', 'pyautogui'),
        ('pyperclip', 'pyperclip'),
        ('pynput',    'pynput'),
        ('qrcode',    'qrcode'),
        ('PIL',       'pillow'),
    ]
    missing = [pip_name for mod, pip_name in required
               if importlib.util.find_spec(mod) is None]
    if not missing:
        return True

    _safe_print(f'📦 检测到缺失依赖: {", ".join(missing)}')

    last_err = ''
    for name, url in PIP_MIRRORS:
        _safe_print(f'📥 正在通过 {name} 镜像源安装...')
        ok, err = _pip_install(missing, index_url=url)
        if ok:
            _safe_print(f'✅ 依赖安装完成（{name}源）')
            return True
        last_err = err
        _safe_print(f'⚠️  {name}源失败，尝试下一个...')

    _safe_print('📥 国内镜像均失败，回退官方 PyPI 源...')
    ok, err = _pip_install(missing)
    if ok:
        _safe_print('✅ 依赖安装完成（官方源）')
        return True
    last_err = err

    _safe_print('❌ 自动安装失败，请手动运行：')
    _safe_print(f'   {sys.executable} -m pip install -i '
                f'https://pypi.tuna.tsinghua.edu.cn/simple {" ".join(missing)}')
    if last_err:
        _safe_print('--- pip 错误输出 ---')
        _safe_print(last_err)
    return False


def _relaunch_without_console():
    if sys.platform != 'win32':
        return
    exe_lower = (sys.executable or '').lower()
    if exe_lower.endswith('pythonw.exe'):
        return
    if not exe_lower.endswith('python.exe'):
        return

    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    except Exception:
        return
    if not hwnd:
        return

    pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    if not os.path.isfile(pyw):
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
        return

    try:
        script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] \
                 else (os.path.abspath(__file__) if '__file__' in globals() else '')
        if not script or not os.path.isfile(script):
            return
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [pyw, script] + sys.argv[1:],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        sys.exit(0)
    except Exception:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


_dep_ok = ensure_dependencies()

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

if not _dep_ok:
    try:
        import tkinter as tk
        from tkinter import messagebox
        _r = tk.Tk(); _r.withdraw()
        messagebox.showerror(
            "依赖安装失败",
            "以下依赖无法自动安装，请手动在命令行执行：\n\n"
            + f'{sys.executable} -m pip install aiohttp pyautogui '
              f'pyperclip pynput qrcode pillow\n\n'
              '窗口将在 5 秒后自动关闭。'
        )
        _r.destroy()
    except Exception:
        pass
    _safe_print('⏳ 5 秒后自动退出，无需按键...')
    try:
        time.sleep(5)
    except Exception:
        pass
    sys.exit(1)

_relaunch_without_console()


# ============== 正式 imports ==============
import asyncio
import socket
import json
import platform
import threading

from aiohttp import web
import aiohttp
import pyautogui
import pyperclip
import qrcode
import tkinter as tk
from tkinter import scrolledtext
from PIL import ImageTk


# ============== 全局状态 ==============
CONFIG = {'port': 5000, 'hotkey': 'f9'}

pyautogui.PAUSE = 0
clipboard_lock = threading.Lock()
connected_clients = set()
client_configs = {}
synced_text = ""
main_loop = None
typing_in_progress = False
rebase_triggered = False
pending_strip_punctuation = False

log_queue = queue.Queue()


# ============== HTML 页面 ==============
HTML_PAGE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>豆包喵喵</title>
    <link href="https://fonts.googleapis.com/css2?family=ZCOOL+KuaiLe&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #FFF9F0;
            --card-bg: #FFFFFF;
            --text-main: #5D4037;
            --text-light: #8D6E63;
            --accent-orange: #FFB74D;
            --accent-red: #FF8A65;
            --btn-bg: #FFFFFF;
            --line-color: #FBE9E7;
            --line-height: 36px;
            --header-height: 40px;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body {
            font-family: 'ZCOOL KuaiLe', cursive, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            height: 100vh;
            display: flex; flex-direction: column;
            padding: 12px 14px; overflow: hidden;
        }
        .disconnect-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(198, 40, 40, 0.88);
            z-index: 99999; display: none;
            align-items: center; justify-content: center;
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
        }
        .disconnect-overlay.show { display: flex; animation: fadeIn 0.25s ease; }
        .disconnect-box {
            background: #fff; border-radius: 24px;
            padding: 36px 32px; text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            max-width: 320px; margin: 20px;
            animation: popIn 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        }
        .disconnect-icon { font-size: 64px; margin-bottom: 16px; animation: shake 1.2s infinite; }
        .disconnect-title { font-size: 22px; font-weight: bold; color: #C62828; margin-bottom: 12px; }
        .disconnect-msg { font-size: 15px; color: #5D4037; margin-bottom: 8px; }
        .disconnect-hint { font-size: 12px; color: #999; margin-top: 12px; line-height: 1.5; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes popIn { from { transform: scale(0.85); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        @keyframes shake {
            0%, 100% { transform: rotate(0deg); }
            25% { transform: rotate(-8deg); }
            75% { transform: rotate(8deg); }
        }
        .header { display: flex; justify-content: space-between; align-items: flex-end; padding-bottom: 5px; margin-bottom: 0; }
        .brand-container { width: 100px; display: flex; justify-content: center; }
        .brand {
            font-size: 26px; display: flex; align-items: center;
            text-shadow: 2px 2px 0px rgba(93, 64, 55, 0.15);
            line-height: 1; white-space: nowrap;
        }
        .status-container { width: 100px; display: flex; justify-content: center; }
        .status-badge {
            font-size: 13px; padding: 4px 10px; border-radius: 14px;
            background: #EFEBE9; color: var(--text-light);
            line-height: 1.2; display: flex; align-items: center;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.03);
            white-space: nowrap;
        }
        .status-badge.connected { background: #C8E6C9; color: #2E7D32; }
        .status-badge.disconnected { background: #FFCDD2; color: #C62828; }
        .help-bubble {
            background: #fff; border: 2px solid #EFEBE9;
            padding: 5px 14px; border-radius: 20px;
            font-size: 13px; color: var(--text-light);
            cursor: pointer; position: relative; bottom: 2px;
            box-shadow: 0 3px 0 #D7CCC8;
            animation: float 3s ease-in-out infinite;
        }
        .help-bubble:active { transform: translateY(3px); box-shadow: none; animation: none; }
        .help-bubble::after {
            content: ''; position: absolute; bottom: -6px; left: 50%; margin-left: -5px;
            width: 0; height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #EFEBE9;
        }
        .help-bubble::before {
            content: ''; position: absolute; bottom: -3px; left: 50%; margin-left: -3px;
            width: 0; height: 0;
            border-left: 3px solid transparent;
            border-right: 3px solid transparent;
            border-top: 4px solid #fff; z-index: 1;
        }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
        .control-area {
            display: flex; justify-content: space-between; align-items: flex-end;
            margin-bottom: -22px; position: relative; z-index: 10;
            padding: 0 4px; margin-top: 15px;
        }
        .capsule-btn {
            background: var(--btn-bg); border: 2px solid #EFEBE9; color: var(--text-main);
            height: 48px; width: 100px; border-radius: 24px;
            display: flex; align-items: center; justify-content: center;
            gap: 6px; font-size: 17px; font-family: inherit;
            box-shadow: 0 4px 0 #D7CCC8; cursor: pointer;
            margin-bottom: 22px; transition: all 0.1s;
        }
        .capsule-btn:active { transform: translateY(4px); box-shadow: none; }
        .capsule-btn.clear {
            background: var(--accent-orange); color: #fff;
            border-color: #FFA726; box-shadow: 0 4px 0 #EF6C00;
        }
        .capsule-btn.clear:active { box-shadow: none; }
        .cat-wrapper {
            width: 130px; height: 85px;
            position: relative; display: flex; justify-content: center; align-items: flex-end;
            transform-origin: bottom center; transform: scale(1.25);
        }
        .cat-head {
            width: 90px; height: 60px; background: var(--text-main);
            border-radius: 45px 45px 35px 35px; position: relative; z-index: 5;
        }
        .cat-ear {
            width: 0; height: 0;
            border-left: 14px solid transparent;
            border-right: 14px solid transparent;
            border-bottom: 22px solid var(--text-main);
            position: absolute; top: -14px;
        }
        .cat-ear.left { left: 6px; transform: rotate(-20deg); }
        .cat-ear.right { right: 6px; transform: rotate(20deg); }
        .cat-ear::after {
            content: ''; position: absolute; top: 6px; left: -5px;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-bottom: 10px solid #FFAB91;
        }
        .cat-face {
            position: absolute; top: 20px; left: 50%; transform: translateX(-50%);
            display: flex; flex-direction: column; align-items: center; width: 100%;
        }
        .eyes-row { display: flex; gap: 24px; }
        .cat-eye {
            width: 10px; height: 10px; background: #fff; border-radius: 50%;
            animation: blink 4s infinite;
            box-shadow: inset 0 0 2px rgba(0,0,0,0.2);
        }
        .cat-nose {
            width: 10px; height: 7px; background: var(--accent-red);
            border-radius: 50% 50% 50% 50% / 30% 30% 70% 70%;
            margin-top: 6px;
        }
        .whiskers {
            position: absolute; top: 30px; left: 50%; transform: translateX(-50%);
            width: 90px; height: 16px;
        }
        .whisker { position: absolute; height: 1px; background: rgba(255,255,255,0.85); }
        .whisker.left-1 { width: 28px; left: 0; top: 3px; transform: rotate(10deg); transform-origin: right center; }
        .whisker.left-2 { width: 28px; left: 0; top: 11px; transform: rotate(-10deg); transform-origin: right center; }
        .whisker.right-1 { width: 28px; right: 0; top: 3px; transform: rotate(-10deg); transform-origin: left center; }
        .whisker.right-2 { width: 28px; right: 0; top: 11px; transform: rotate(10deg); transform-origin: left center; }
        .cat-paw {
            width: 26px; height: 18px; background: #FFF8E1;
            border-radius: 13px 13px 8px 8px;
            border: 2px solid var(--text-main); border-bottom: none;
            position: absolute; bottom: 0; z-index: 20;
            box-shadow: 0 2px 4px rgba(0,0,0,0.12);
        }
        .cat-paw.left { left: 22px; }
        .cat-paw.right { right: 22px; }
        .cat-paw::before {
            content: ''; position: absolute; top: 4px; left: 50%; transform: translateX(-50%);
            width: 8px; height: 6px; background: #FFCCBC; border-radius: 50%;
        }
        .typing .cat-paw.left { animation: tap 0.15s infinite alternate; }
        .typing .cat-paw.right { animation: tap 0.15s infinite alternate-reverse; }
        @keyframes tap { to { transform: translateY(6px); } }
        @keyframes blink { 0%, 96%, 100% { transform: scaleY(1); } 98% { transform: scaleY(0.1); } }
        .paper-card {
            flex: 1; background: var(--card-bg); border-radius: 20px;
            box-shadow: 0 4px 15px rgba(93,64,55,0.08);
            border: 4px solid #EFEBE9;
            display: flex; flex-direction: column;
            padding: 0 4px 10px;
            position: relative; z-index: 1;
        }
        textarea {
            flex: 1; width: 100%; border: none; outline: none; resize: none;
            background: transparent;
            font-family: 'ZCOOL KuaiLe', cursive;
            font-size: 22px; color: var(--text-main);
            line-height: var(--line-height);
            padding: 0 16px; padding-top: var(--header-height);
            background-image:
                linear-gradient(to bottom, var(--card-bg) var(--header-height), transparent var(--header-height)),
                repeating-linear-gradient(
                    transparent, transparent calc(var(--line-height) - 1px),
                    var(--line-color) calc(var(--line-height) - 1px),
                    var(--line-color) var(--line-height)
                );
            background-attachment: local;
            background-position: 0 -4px;
            caret-color: var(--text-main);
        }
        textarea::placeholder { color: #D7CCC8; font-size: 20px; }
        .info-bar {
            text-align: right; padding: 5px 16px 0; font-size: 12px; color: #BCAAA4;
            display: flex; justify-content: space-between;
        }
        .footer-credit { text-align: center; font-size: 11px; color: #D7CCC8; margin-top: 8px; }
        .modal-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(93, 64, 55, 0.4); z-index: 999;
            display: none; align-items: center; justify-content: center;
            backdrop-filter: blur(2px);
        }
        .modal {
            background: #fff; width: 85%; max-width: 320px;
            border-radius: 24px; padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            animation: popUp 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        }
        @keyframes popUp { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-size: 16px; }
        .setting-input {
            width: 70px; padding: 6px; border: 2px solid #EFEBE9;
            border-radius: 8px; text-align: center; font-family: inherit;
            font-size: 16px; color: var(--text-main);
        }
        .modal-btn {
            width: 100%; padding: 10px; background: var(--accent-orange);
            color: #fff; border: none; border-radius: 12px;
            font-family: inherit; font-size: 16px; margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="disconnect-overlay" id="disconnectOverlay">
        <div class="disconnect-box">
            <div class="disconnect-icon">⚠️</div>
            <div class="disconnect-title">与服务端失联</div>
            <div class="disconnect-msg" id="reconnectMsg">正在尝试重新连接...</div>
            <div class="disconnect-hint">请确认电脑端「豆包喵喵」程序仍在运行，<br>且手机与电脑处于同一 Wi-Fi 下。</div>
        </div>
    </div>

    <div class="header">
        <div class="brand-container"><div class="brand">豆包喵喵</div></div>
        <div class="help-bubble" id="helpBtn">使用帮助?</div>
        <div class="status-container">
            <div class="status-badge disconnected" id="status">断开</div>
        </div>
    </div>

    <div class="control-area">
        <button class="capsule-btn" id="settingsBtn"><span>⚙️</span> 设置</button>
        <div class="cat-wrapper" id="catAnim">
            <div class="cat-head">
                <div class="cat-ear left"></div>
                <div class="cat-ear right"></div>
                <div class="cat-face">
                    <div class="eyes-row">
                        <div class="cat-eye"></div>
                        <div class="cat-eye"></div>
                    </div>
                    <div class="cat-nose"></div>
                </div>
                <div class="whiskers">
                    <div class="whisker left-1"></div>
                    <div class="whisker left-2"></div>
                    <div class="whisker right-1"></div>
                    <div class="whisker right-2"></div>
                </div>
            </div>
            <div class="cat-paw left"></div>
            <div class="cat-paw right"></div>
        </div>
        <button class="capsule-btn clear" id="clearBtn"><span>🗑️</span> 清空</button>
    </div>

    <div class="paper-card">
        <textarea id="input"
            placeholder="点击这里，告诉猫猫你想写什么..."
            autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
        ></textarea>
        <div class="info-bar">
            <span id="timer"></span>
            <span id="stats">已同步 0 字</span>
        </div>
    </div>

    <div class="footer-credit">Claude和Gemini共同制作的豆包输入法同步程序</div>

    <div class="modal-overlay" id="settingsModal">
        <div class="modal">
            <h3 style="text-align:center; margin-bottom:20px;">⚙️ 喵喵设置</h3>
            <div class="setting-row">
                <span>删除/修改合并 (ms)</span>
                <input type="number" class="setting-input" id="debounceDelay" value="200" step="50">
            </div>
            <div class="setting-row">
                <span>自动清空 (s)</span>
                <input type="number" class="setting-input" id="autoClearDelay" value="0" placeholder="0禁用">
            </div>
            <div class="setting-row">
                <span>检测电脑键盘</span>
                <input type="checkbox" id="detectKeyboard" style="width:20px; height:20px;" checked>
            </div>
            <button class="modal-btn" onclick="closeModal('settingsModal')">保存设置</button>
        </div>
    </div>

    <div class="modal-overlay" id="helpModal">
        <div class="modal">
            <h3 style="text-align:center; margin-bottom:15px;">📖 使用指南</h3>
            <ul style="padding-left: 20px; line-height: 1.6; font-size: 14px; color: var(--text-main);">
                <li style="margin-bottom:8px"><b>基本用法：</b>在横线纸上语音或打字，文字会实时“飞”到电脑光标处。</li>
                <li style="margin-bottom:8px"><b>上屏节奏：</b>新增一个字就立即上屏；删除或替换会在「合并时间」内合并成一次操作。</li>
                <li style="margin-bottom:8px"><b>回车换行：</b>手机按回车，电脑端会同步发送一个换行，并在手机上清空输入框。</li>
                <li style="margin-bottom:8px"><b>如何清空：</b>手机点「清空」、按换行键，或电脑按 <b style="background:#eee;padding:0 4px;border-radius:4px">F9</b> 均可。</li>
                <li style="margin-bottom:8px"><b>电脑介入（智能续写）：</b><br>当你操作电脑（打字/点击）后，手机会自动“翻篇”，下次输入将作为新段落发送，<b>不会</b>修改你刚才在电脑上编辑的内容。</li>
                <li><b>设置小贴士：</b><br>
                    • <b>删除/修改合并</b>：200ms 已足够合并快速纠错，若觉得删除慢可调到 100ms。<br>
                    • <b>检测键盘</b>：开启后才能使用“电脑介入”功能。
                </li>
            </ul>
            <button class="modal-btn" onclick="closeModal('helpModal')">明白啦</button>
        </div>
    </div>

    <script>
        const input = document.getElementById('input');
        const status = document.getElementById('status');
        const stats = document.getElementById('stats');
        const timer = document.getElementById('timer');
        const catAnim = document.getElementById('catAnim');
        const disconnectOverlay = document.getElementById('disconnectOverlay');
        const reconnectMsg = document.getElementById('reconnectMsg');

        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }

        document.getElementById('settingsBtn').onclick = () => openModal('settingsModal');
        document.getElementById('helpBtn').onclick = () => openModal('helpModal');
        document.querySelectorAll('.modal-overlay').forEach(el =>
            el.onclick = (e) => { if (e.target === el) closeModal(el.id); });
        document.getElementById('clearBtn').onclick = performClearWithBlur;

        const debounceDelayInput = document.getElementById('debounceDelay');
        const autoClearDelayInput = document.getElementById('autoClearDelay');
        const detectKeyboardInput = document.getElementById('detectKeyboard');

        function saveSettings() {
            localStorage.setItem('debounceDelay', debounceDelayInput.value);
            localStorage.setItem('autoClearDelay', autoClearDelayInput.value);
            localStorage.setItem('detectKeyboard', detectKeyboardInput.checked);
        }
        function loadSettings() {
            const s1 = localStorage.getItem('debounceDelay');
            const s2 = localStorage.getItem('autoClearDelay');
            const s3 = localStorage.getItem('detectKeyboard');
            if (s1) debounceDelayInput.value = s1;
            if (s2) autoClearDelayInput.value = s2;
            if (s3 !== null) detectKeyboardInput.checked = s3 === 'true';
        }
        [debounceDelayInput, autoClearDelayInput].forEach(el =>
            el.addEventListener('change', saveSettings));
        detectKeyboardInput.addEventListener('change', () => {
            saveSettings();
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'config',
                    detectKeyboard: detectKeyboardInput.checked }));
            }
        });
        loadSettings();

        let ws = null, lastSentText = '', totalSent = 0, ignoreLength = 0;
        let debounceTimer = null, autoClearTimer = null, enterConfirmTimer = null;
        let autoClearCountdown = 0, reconnectCount = 0;

        function showDisconnect() {
            reconnectCount++;
            reconnectMsg.textContent = `正在尝试重新连接...（第 ${reconnectCount} 次）`;
            disconnectOverlay.classList.add('show');
        }
        function hideDisconnect() {
            reconnectCount = 0;
            disconnectOverlay.classList.remove('show');
        }

        function connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            ws.onopen = () => {
                hideDisconnect();
                status.textContent = '已连接';
                status.className = 'status-badge connected';
                ws.send(JSON.stringify({
                    type: 'config',
                    detectKeyboard: detectKeyboardInput.checked
                }));
            };
            ws.onclose = () => {
                showDisconnect();
                status.textContent = '断开';
                status.className = 'status-badge disconnected';
                setTimeout(connect, 2000);
            };
            ws.onerror = () => ws.close();
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'clear') performClear();
                else if (data.type === 'clear_with_blur') performClearWithBlur();
                else if (data.type === 'rebase') {
                    ignoreLength = input.value.length;
                    lastSentText = '';
                    status.textContent = '电脑介入';
                    setTimeout(() => {
                        if (ws.readyState === 1) status.textContent = '已连接';
                    }, 2000);
                }
            };
        }

        function performClear() {
            if (debounceTimer) clearTimeout(debounceTimer);
            sendTextDiff();
            input.value = ''; ignoreLength = 0; lastSentText = '';
            if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'reset' }));
            if (autoClearTimer) { clearInterval(autoClearTimer); timer.textContent = ''; }
        }
        function performClearAfterEnter() {
            if (debounceTimer) clearTimeout(debounceTimer);
            input.value = ''; ignoreLength = 0; lastSentText = '';
            if (autoClearTimer) { clearInterval(autoClearTimer); timer.textContent = ''; }
        }
        function performClearWithBlur() {
            performClear(); input.blur();
            requestAnimationFrame(() => requestAnimationFrame(() => input.focus()));
        }

        // 核心调度：
        //   新增字（delta > 0）→ 立即发送，实现"一个字一个字实时上屏"
        //   删除/替换（delta <= 0）→ 走时间兜底，连续修正合并成一次操作
        //   注意：完全不使用 isComposing 判断，语音输入法会一直把它置为 true
        function scheduleSend() {
            if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }

            const full = input.value;
            const effectiveLen = full.length - Math.min(ignoreLength, full.length);
            const delta = effectiveLen - lastSentText.length;

            if (delta > 0) {
                // 有新增字符，立即上屏
                sendTextDiff();
                catAnim.classList.remove('typing');
                return;
            }

            // 删除 / 替换：等一小段时间合并连续操作
            const delay = parseInt(debounceDelayInput.value) || 200;
            debounceTimer = setTimeout(() => {
                debounceTimer = null;
                sendTextDiff();
                catAnim.classList.remove('typing');
            }, delay);
        }

        input.addEventListener('input', () => {
            catAnim.classList.add('typing');
            scheduleSend();

            const acDelay = parseInt(autoClearDelayInput.value) || 0;
            if (autoClearTimer) clearInterval(autoClearTimer);
            if (acDelay > 0 && input.value) {
                autoClearCountdown = acDelay;
                timer.textContent = `${autoClearCountdown}s后清空`;
                autoClearTimer = setInterval(() => {
                    autoClearCountdown--;
                    if (autoClearCountdown <= 0) {
                        clearInterval(autoClearTimer);
                        performClearWithBlur();
                    } else timer.textContent = `${autoClearCountdown}s后清空`;
                }, 1000);
            } else timer.textContent = '';
        });

        function sendTextDiff() {
            const full = input.value;
            if (full.length < ignoreLength) ignoreLength = full.length;
            const effective = full.substring(ignoreLength);
            if (effective === lastSentText) return;
            if (ws && ws.readyState === 1) {
                ws.send(JSON.stringify({
                    type: 'diff', oldText: lastSentText, newText: effective
                }));
                const diff = effective.length - lastSentText.length;
                if (diff > 0) totalSent += diff;
                stats.textContent = `已同步 ${totalSent} 字`;
                lastSentText = effective;
            }
        }

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (enterConfirmTimer) clearTimeout(enterConfirmTimer);
                sendTextDiff();
                if (ws && ws.readyState === 1) {
                    ws.send(JSON.stringify({ type: 'enter' }));
                }
                enterConfirmTimer = setTimeout(() => {
                    enterConfirmTimer = null;
                    performClearAfterEnter();
                }, 300);
            }
        });

        connect();
        window.onload = () => setTimeout(() => input.focus(), 100);
    </script>
</body>
</html>
'''


# ============== 工具函数 ==============
def get_local_ip():
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            if ip.startswith('192.168.') or ip.startswith('10.'):
                return ip
        for ip in ips:
            if ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31:
                return ip
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def compute_diff(old, new):
    common = 0
    for i in range(min(len(old), len(new))):
        if old[i] == new[i]:
            common += 1
        else:
            break
    return len(old) - common, new[common:]


def type_text(text):
    global typing_in_progress
    if not text:
        return
    typing_in_progress = True
    try:
        with clipboard_lock:
            try:
                orig = pyperclip.paste()
            except Exception:
                orig = ''
            pyperclip.copy(text)
            if platform.system() == 'Darwin':
                pyautogui.hotkey('command', 'v')
            else:
                pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            try:
                pyperclip.copy(orig)
            except Exception:
                pass
    finally:
        typing_in_progress = False


def send_backspaces(count):
    global typing_in_progress
    if count <= 0:
        return
    typing_in_progress = True
    try:
        for i in range(count):
            pyautogui.press('backspace')
            if i < count - 1:
                time.sleep(0.005)
    finally:
        typing_in_progress = False


def send_enter():
    global typing_in_progress
    if typing_in_progress:
        return
    typing_in_progress = True
    try:
        pyautogui.press('enter')
    finally:
        typing_in_progress = False


# ============== aiohttp 请求处理 ==============
async def handle_index(req):
    return web.Response(text=HTML_PAGE, content_type='text/html')


async def handle_websocket(req):
    global synced_text, rebase_triggered, pending_strip_punctuation
    ws = web.WebSocketResponse()
    await ws.prepare(req)
    connected_clients.add(ws)
    print('📱 手机已连接')
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get('type') == 'config':
                    client_configs[ws] = {
                        'detect_keyboard': data.get('detectKeyboard')
                    }
                elif data.get('type') == 'diff':
                    new_txt = data.get('newText', '')
                    d_cnt, add_txt = compute_diff(synced_text, new_txt)
                    if pending_strip_punctuation and d_cnt == 0 and add_txt:
                        punctuations = "，。、；：？！""''·…—～,.;:?!'\""
                        if add_txt[0] in punctuations:
                            add_txt = add_txt[1:]
                            print('✂️ 去除开头标点')
                        pending_strip_punctuation = False
                    rebase_triggered = False
                    if d_cnt:
                        send_backspaces(d_cnt)
                        print(f'⌫ {d_cnt}')
                    if add_txt:
                        type_text(add_txt)
                        print(f'⌨️ {add_txt}')
                    synced_text = new_txt
                elif data.get('type') == 'enter':
                    send_enter()
                    synced_text = ""
                    rebase_triggered = False
                    pending_strip_punctuation = True
                    print('↵ 回车并重置')
                elif data.get('type') == 'reset':
                    synced_text = ""
                    pending_strip_punctuation = True
                    print('🔄 重置')
    finally:
        connected_clients.discard(ws)
        client_configs.pop(ws, None)
        print('📱 断开')
    return ws


async def broadcast_clear_with_blur():
    for ws in list(connected_clients):
        try:
            await ws.send_json({'type': 'clear_with_blur'})
        except Exception:
            pass


async def broadcast_rebase():
    for ws in list(connected_clients):
        try:
            await ws.send_json({'type': 'rebase'})
        except Exception:
            pass


def reset_synced_text():
    global synced_text, rebase_triggered, pending_strip_punctuation
    if typing_in_progress:
        return
    if rebase_triggered:
        return
    if synced_text:
        synced_text = ""
        rebase_triggered = True
        pending_strip_punctuation = True
        print('🔄 电脑端输入，触发增量同步')
        if main_loop:
            asyncio.run_coroutine_threadsafe(broadcast_rebase(), main_loop)


def setup_hotkey():
    hotkey = CONFIG.get('hotkey', '').strip()
    IGNORED = {
        'shift', 'ctrl', 'alt', 'cmd', 'num_lock', 'scroll_lock',
        'home', 'end', 'page_up', 'page_down', 'insert', 'escape',
        'print_screen', 'pause',
        'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9',
        'f10', 'f11', 'f12',
    }
    try:
        from pynput import keyboard, mouse

        def on_press(key):
            try:
                k = key.char if hasattr(key, 'char') else key.name
                if not k:
                    return
                if hotkey and k.lower() == hotkey.lower():
                    if main_loop:
                        asyncio.run_coroutine_threadsafe(
                            broadcast_clear_with_blur(), main_loop)
                    return
                if k.lower() not in IGNORED and any(
                    c.get('detect_keyboard')
                    for c in client_configs.values()
                ):
                    reset_synced_text()
            except Exception:
                pass

        def on_click(x, y, button, pressed):
            try:
                if button == mouse.Button.left and pressed:
                    if any(c.get('detect_keyboard')
                           for c in client_configs.values()):
                        reset_synced_text()
            except Exception:
                pass

        keyboard.Listener(on_press=on_press).start()
        mouse.Listener(on_click=on_click).start()
        if hotkey:
            print(f'🎹 热键: [{hotkey}]')
        print('🖱️ 鼠标左键监测已启用')
    except Exception:
        print('⚠️  热键需安装 pynput')


# ============== asyncio 服务端 ==============
async def server_main(port):
    global main_loop
    main_loop = asyncio.get_event_loop()

    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/ws', handle_websocket)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', port).start()

    print('=' * 44)
    print('🚀 豆包喵喵服务已启动')
    print(f'📱 手机访问: http://{get_local_ip()}:{port}')
    print('📷 扫描窗口内二维码即可打开')
    print('=' * 44)

    setup_hotkey()
    while True:
        await asyncio.sleep(3600)


def run_asyncio_loop(port):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server_main(port))
    except Exception as e:
        print(f'❌ 服务异常退出: {e}')


# ============== stdout 重定向到 GUI 日志 ==============
class QueueWriter:
    def __init__(self, q):
        self.q = q
        self.buffer = ''

    def write(self, text):
        if not text:
            return
        self.buffer += text
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.q.put(line)

    def flush(self):
        if self.buffer:
            self.q.put(self.buffer)
            self.buffer = ''

    def isatty(self):
        return False


# ============== GUI 主窗口 ==============
def make_qr_image(url, box_size=8):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    if hasattr(img, 'get_image'):
        img = img.get_image()
    return img.convert('RGB')


def run_gui(url, port):
    if platform.system() == 'Windows':
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    root.title("豆包喵喵 · 语音输入")
    root.configure(bg='#FFF9F0')
    root.update_idletasks()

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    win_w = max(int(screen_w / 2), 640)
    win_h = max(int(screen_h * 2 / 3), 600)

    x = (screen_w - win_w) // 2
    y = (screen_h - win_h) // 2
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")
    root.minsize(420, 480)

    header = tk.Frame(root, bg='#FFF9F0')
    header.pack(fill='x', padx=16, pady=(12, 4))
    tk.Label(
        header, text="🐱 豆包喵喵",
        font=("Microsoft YaHei", 20, "bold"),
        bg='#FFF9F0', fg='#5D4037'
    ).pack()
    tk.Label(
        header, text="手机语音输入 · 电脑实时上屏",
        font=("Microsoft YaHei", 10),
        bg='#FFF9F0', fg='#8D6E63'
    ).pack(pady=(2, 0))

    qr_frame = tk.Frame(
        root, bg='white',
        highlightbackground='#EFEBE9', highlightthickness=2
    )
    qr_frame.pack(pady=10)
    try:
        qr_img = make_qr_image(url, box_size=8)
        qr_photo = ImageTk.PhotoImage(qr_img)
        qr_label = tk.Label(qr_frame, image=qr_photo, bg='white')
        qr_label.image = qr_photo
        qr_label.pack(padx=10, pady=10)
    except Exception as e:
        tk.Label(
            qr_frame, text=f"二维码生成失败：{e}",
            bg='white', fg='#C62828', font=("Microsoft YaHei", 10)
        ).pack(padx=20, pady=20)

    url_var = tk.StringVar(value=url)
    url_entry = tk.Entry(
        root, textvariable=url_var,
        font=("Consolas", 12), justify='center',
        state='readonly', readonlybackground='#FFF9F0',
        relief='flat', bd=0, fg='#5D4037',
    )
    url_entry.pack(pady=(0, 4), padx=20, fill='x')

    tk.Label(
        root, text="📱 手机相机 / 微信扫一扫即可打开",
        font=("Microsoft YaHei", 9),
        bg='#FFF9F0', fg='#8D6E63'
    ).pack(pady=(0, 6))

    log_frame = tk.Frame(root, bg='#FFF9F0')
    log_frame.pack(fill='both', expand=True, padx=16, pady=(4, 12))

    tk.Label(
        log_frame, text="运行日志",
        font=("Microsoft YaHei", 10, "bold"),
        bg='#FFF9F0', fg='#5D4037', anchor='w'
    ).pack(fill='x')

    log_widget = scrolledtext.ScrolledText(
        log_frame, height=12,
        font=("Consolas", 9),
        bg='#FFFFFF', fg='#5D4037',
        relief='flat', bd=0,
        highlightbackground='#EFEBE9', highlightthickness=2,
        padx=8, pady=8,
        state='disabled',
    )
    log_widget.pack(fill='both', expand=True, pady=(4, 0))

    def poll_logs():
        try:
            count = 0
            while count < 100:
                try:
                    line = log_queue.get_nowait()
                except queue.Empty:
                    break
                log_widget.config(state='normal')
                log_widget.insert('end', line + '\n')
                log_widget.config(state='disabled')
                count += 1
            if count > 0:
                log_widget.see('end')

            total_lines = int(log_widget.index('end-1c').split('.')[0])
            if total_lines > 1000:
                log_widget.config(state='normal')
                log_widget.delete('1.0', '501.0')
                log_widget.config(state='disabled')
        except Exception:
            pass
        root.after(150, poll_logs)

    for line in _dep_logs:
        log_queue.put(line)
    _dep_logs.clear()

    sys.stdout = QueueWriter(log_queue)
    sys.stderr = QueueWriter(log_queue)

    print(f'🖥️ 检测到屏幕: {screen_w} × {screen_h}')
    print(f'🪟 窗口尺寸: {win_w} × {win_h}')
    print('   （宽度 = 屏幕 1/2，高度 = 屏幕 2/3）')
    print('⚡ 上屏策略：追加字立即发送，删除/替换走 200ms 合并')
    print('💡 提示：把本文件重命名为 server.pyw 后双击，可完全避免启动瞬间的黑框')

    threading.Thread(
        target=run_asyncio_loop, args=(port,), daemon=True
    ).start()

    poll_logs()

    def on_close():
        try:
            root.destroy()
        finally:
            os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ============== 入口 ==============
def _safe_sleep(seconds):
    try:
        time.sleep(seconds)
    except Exception:
        pass


def main():
    try:
        port = CONFIG['port']
        url = f'http://{get_local_ip()}:{port}'
        run_gui(url, port)
    except KeyboardInterrupt:
        print('\n👋 已退出')
    except Exception:
        import traceback
        traceback.print_exc()
        print('\n⏳ 5 秒后自动退出，无需按键...')
        _safe_sleep(5)
        sys.exit(1)


if __name__ == '__main__':
    main()
