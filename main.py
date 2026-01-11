from flask import Flask, request, render_template_string, jsonify
import pyautogui
import pyperclip
import socket
import re
import os
import sys
# 新增：导入二维码生成库
import qrcode
from qrcode.console_scripts import main as qr_main

app = Flask(__name__)

# 存储正则替换规则（key: 编译后的正则表达式，value: 替换式）
REPLACE_RULES = []

# ===== 重构历史记录：存储上一次操作的类型和内容 =====
# 格式: {"type": "text"/"enter"/"delete", "content": 文本内容/空字符串}
LAST_OPERATION = {"type": None, "content": ""}

def load_replace_rules():
    """加载 EXE 所在目录下的 hot-rule.txt 替换规则"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    
    rule_file = os.path.join(exe_dir, "hot-rule.txt")
    if not os.path.exists(rule_file):
        print(f"警告：未找到规则文件 {rule_file}，跳过规则加载")
        return
    
    with open(rule_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = re.split(r'\s+=\s+', line, maxsplit=1)
        if len(parts) != 2:
            print(f"警告：第 {line_num} 行格式错误，跳过该规则")
            continue
        pattern_str, replace_str = parts[0].strip(), parts[1].strip()
        try:
            pattern = re.compile(pattern_str)
            REPLACE_RULES.append( (pattern, replace_str) )
            print(f"加载规则成功：{pattern_str} → {replace_str}")
        except re.error as e:
            print(f"警告：第 {line_num} 行正则错误 {e}，跳过该规则")

load_replace_rules()

def apply_replace_rules(text):
    """应用所有替换规则到文本"""
    for pattern, replace_str in REPLACE_RULES:
        text = pattern.sub(replace_str, text)
    return text

def paste_text(text):
    """剪贴板粘贴方案，兼容中文"""
    original_clipboard = pyperclip.paste()
    try:
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
    finally:
        pyperclip.copy(original_clipboard)

# ===== 重构撤销函数：根据操作类型执行不同撤销逻辑 =====
def undo_last_operation():
    """
    根据 LAST_OPERATION 的类型执行撤销
    - text: 删除对应长度的字符
    - enter: 模拟删除换行（按一次 backspace，多数编辑器换行占1个删除单位）
    - delete: 无撤销（因为是主动删除PC端内容，无历史文本可恢复）
    """
    op_type = LAST_OPERATION["type"]
    content = LAST_OPERATION["content"]
    
    if op_type == "text":
        # 文本操作：删除替换后的文本长度
        replaced_len = len(apply_replace_rules(content))
        if replaced_len > 0:
            pyautogui.press('backspace', presses=replaced_len)
    elif op_type == "enter":
        # 回车操作：按一次 backspace 撤销换行
        pyautogui.press('backspace')
    elif op_type == "delete":
        # 删除操作：无撤销逻辑，直接清空历史
        pass

# ===== 新增：方向键控制接口 =====
@app.route('/move_cursor', methods=['POST'])
def move_cursor():
    direction = request.json.get('direction')
    # 使用 pyautogui 模拟方向键按下
    if direction in ['left', 'up', 'down', 'right']:
        pyautogui.press(direction)
        print(f"执行光标移动：{direction}")
    return jsonify({"status": "success"})

# ===== 新增：PC端删除接口 =====
@app.route('/delete_pc', methods=['POST'])
def delete_pc():
    global LAST_OPERATION
    # 执行 PC 端删除（backspace）
    pyautogui.press('backspace')
    # 记录删除操作，且标记为不可撤销（避免和撤销逻辑冲突）
    LAST_OPERATION = {"type": "delete", "content": ""}
    print("执行PC端删除操作")
    return jsonify({"status": "success"})

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>手机-电脑输入同步（支持模式切换）</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 0;
            background-color: #f0f0f0;
            margin: 0;
            font-size: 16px;
            /* 模式切换变量 */
            --base-font: 1rem;
            --input-height: 150px;
            --input-font: 1.1rem;
            --input-padding: 15px;
            --btn-padding: 12px 8px;
            --btn-font: 1rem;
            --btn-min-height: 60px;
            --btn-min-width: 80px;
            --btn-gap: 8px;
            --btn-margin-top: 15px;
            --border-radius: 8px;
            /* 新增：底部按钮间距 */
            padding-bottom: 30px;
        }
        /* 手机模式样式（超大尺寸） */
        body.phone-mode {
            --base-font: 18px;
            --input-height: 280px;
            --input-font: 2rem;
            --input-padding: 25px;
            --btn-padding: 28px 15px;
            --btn-font: 2rem;
            --btn-min-height: 80px;
            --btn-min-width: 90px;
            --btn-gap: 12px;
            --btn-margin-top: 25px;
            --border-radius: 12px;
        }
        /* 平板模式样式（适中尺寸） */
        body.tablet-mode {
            --base-font: 18px;
            --input-height: 180px;
            --input-font: 1.2rem;
            --input-padding: 20px;
            --btn-padding: 18px 10px;
            --btn-font: 1.2rem;
            --btn-min-height: 70px;
            --btn-min-width: 85px;
            --btn-gap: 10px;
            --btn-margin-top: 20px;
            --border-radius: 10px;
        }
        #mode-switch-btn {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 8px 15px;
            background-color: #ff9800;
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 14px;
            cursor: pointer;
            z-index: 999;
        }
        #input-box {
            width: 90%;
            height: var(--input-height);
            padding: var(--input-padding);
            border: 2px solid #4CAF50;
            border-radius: var(--border-radius);
            resize: none;
            font-size: var(--input-font);
        }
        .btn-group {
            width: 90%;
            margin-top: var(--btn-margin-top);
            display: flex;
            gap: var(--btn-gap);
            flex-wrap: wrap;
        }
        .func-btn, .dir-btn, .symbol-btn {
            flex: 1;
            padding: var(--btn-padding);
            border: none;
            border-radius: var(--border-radius);
            cursor: pointer;
            color: white;
            white-space: nowrap;
            min-width: var(--btn-min-width);
            min-height: var(--btn-min-height);
            font-size: var(--btn-font);
        }
        .func-btn {
            background-color: #4CAF50;
        }
        #send-enter-btn {
            background-color: #2196F3;
        }
        #undo-btn {
            background-color: #9E9E9E;
        }
        #undo-btn.enabled {
            background-color: #4CAF50;
        }
        #clear-btn {
            background-color: #f44336;
        }
        .dir-btn {
            background-color: #333;
            font-weight: bold;
        }
        .symbol-btn {
            background-color: #9c27b0;
        }
        .func-btn:active, .dir-btn:active, .symbol-btn:active {
            opacity: 0.8;
            transform: scale(0.98);
        }
        /* 弹出层样式 */
        #symbol-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-content {
            width: 85%;
            background-color: white;
            padding: var(--input-padding);
            border-radius: var(--border-radius);
            gap: 20px;
            display: flex;
            flex-direction: column;
        }
        #symbol-input {
            padding: var(--input-padding);
            font-size: var(--input-font);
            border: 2px solid #4CAF50;
            border-radius: var(--border-radius);
        }
        #confirm-symbol {
            padding: var(--btn-padding);
            font-size: var(--btn-font);
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: var(--border-radius);
            cursor: pointer;
        }
        /* 新增：底部唤起键盘按钮样式 */
        #show-keyboard-btn {
            margin-top: 20px;
            padding: var(--btn-padding);
            font-size: var(--btn-font);
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: var(--border-radius);
            min-width: var(--btn-min-width);
            min-height: var(--btn-min-height);
            cursor: pointer;
        }
        #show-keyboard-btn:active {
            opacity: 0.8;
            transform: scale(0.98);
        }
    </style>
</head>
<body class="phone-mode">
    <!-- 模式切换按钮 -->
    <button id="mode-switch-btn" onclick="toggleMode()">布局：大</button>

    <textarea id="input-box" placeholder="请输入内容，随后按回车键发送。输入框为空时，回车为PC换行，删除为PC删除。（支持正则替换，规则在 hot-rule.txt 中配置）..."></textarea>
    <!-- 功能按钮组 -->
    <div class="btn-group">
        <button class="func-btn" id="send-text-btn" onclick="sendText()">发送</button>
        <button class="func-btn" id="send-enter-btn" onclick="sendEnter()">回车</button>
        <button class="func-btn" id="undo-btn" onclick="undoLast()" disabled>撤销</button>
        <button class="func-btn" id="clear-btn" onclick="clearInput()">清空</button>
    </div>
    <!-- 方向按钮组：箭头图标 -->
    <div class="btn-group">
        <button class="dir-btn" onclick="moveCursor('left')">←</button>
        <button class="dir-btn" onclick="moveCursor('up')">↑</button>
        <button class="dir-btn" onclick="moveCursor('down')">↓</button>
        <button class="dir-btn" onclick="moveCursor('right')">→</button>
    </div>
    <!-- 成对符号按钮组 -->
    <div class="btn-group">
        <button class="symbol-btn" onclick="openSymbolModal('()')">（）</button>
        <button class="symbol-btn" onclick="openSymbolModal('“”')">“”</button>
        <button class="symbol-btn" onclick="openSymbolModal('「」')">「」</button>
        <button class="symbol-btn" onclick="openSymbolModal('[]')">[]</button>
    </div>
    <!-- 新增：底部唤起键盘按钮 -->
    <button id="show-keyboard-btn" onclick="focusInputAndShowKeyboard()">唤起键盘</button>

    <!-- 弹出输入框遮罩 -->
    <div id="symbol-modal">
        <div class="modal-content">
            <input type="text" id="symbol-input" placeholder="请输入对话或提示内容，按回车键跳出对话框..." />
            <button id="confirm-symbol" onclick="confirmSymbol()">确认</button>
        </div>
    </div>

    <script>
        let hasHistory = false;
        let currentSymbol = "";
        let currentMode = "phone-mode"; // 默认手机模式

        // 模式切换核心函数
        function toggleMode() {
            const body = document.body;
            const btn = document.getElementById('mode-switch-btn');
            if (currentMode === "phone-mode") {
                body.classList.remove("phone-mode");
                body.classList.add("tablet-mode");
                currentMode = "tablet-mode";
                btn.textContent = "布局：小";
            } else {
                body.classList.remove("tablet-mode");
                body.classList.add("phone-mode");
                currentMode = "phone-mode";
                btn.textContent = "布局：大";
            }
        }

        function updateUndoBtn() {
            const btn = document.getElementById('undo-btn');
            if (hasHistory) {
                btn.classList.add('enabled');
                btn.disabled = false;
            } else {
                btn.classList.remove('enabled');
                btn.disabled = true;
            }
        }

        function sendText() {
            const text = document.getElementById('input-box').value.trim();
            if (!text) return;
            fetch('/send', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: text})
            }).then(() => {
                hasHistory = true;
                updateUndoBtn();
                document.getElementById('input-box').value = '';
            });
        }

        function sendEnter() {
            fetch('/send_enter', {method: 'POST'}).then(() => {
                hasHistory = true;
                updateUndoBtn();
            });
        }

        function undoLast() {
            fetch('/undo', {method: 'POST'}).then(response => response.json()).then(data => {
                if (data.status === 'success') {
                    document.getElementById('input-box').value = data.content || '';
                    hasHistory = false;
                    updateUndoBtn();
                }
            });
        }

        function clearInput() {
            document.getElementById('input-box').value = '';
        }

        function moveCursor(direction) {
            fetch('/move_cursor', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({direction: direction})
            }).then(() => {
                hasHistory = false;
                updateUndoBtn();
            });
        }

        // 新增：调用PC端删除接口
        function sendDelete() {
            fetch('/delete_pc', {method: 'POST'}).then(() => {
                hasHistory = false; // 触发删除后重置历史，撤回按钮变灰
                updateUndoBtn();
            });
        }

        function openSymbolModal(symbol) {
            currentSymbol = symbol;
            const modal = document.getElementById('symbol-modal');
            const input = document.getElementById('symbol-input');
            input.value = '';
            modal.style.display = 'flex';
            setTimeout(() => input.focus(), 100);
        }

        function insertAtCursor(text) {
            const input = document.getElementById('input-box');
            const startPos = input.selectionStart;
            const endPos = input.selectionEnd;
            const value = input.value;
            input.value = value.substring(0, startPos) + text + value.substring(endPos);
            input.selectionStart = input.selectionEnd = startPos + text.length;
            input.focus();
        }

        function confirmSymbol() {
            const input = document.getElementById('symbol-input');
            const content = input.value.trim();
            if (!content) {
                document.getElementById('symbol-modal').style.display = 'none';
                return;
            }
            const leftSymbol = currentSymbol.substring(0, currentSymbol.length / 2);
            const rightSymbol = currentSymbol.substring(currentSymbol.length / 2);
            const wrappedText = leftSymbol + content + rightSymbol;
            insertAtCursor(wrappedText);
            document.getElementById('symbol-modal').style.display = 'none';
        }

        // 新增：唤起键盘并聚焦输入框函数
        function focusInputAndShowKeyboard() {
            const inputBox = document.getElementById('input-box');
            // 聚焦输入框，移动端会自动弹出键盘
            inputBox.focus();
            // 滚动到输入框位置（可选，防止按钮遮挡）
            inputBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        // 回车确认
        document.getElementById('symbol-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmSymbol();
            }
        });

        // 点击遮罩关闭弹窗
        document.getElementById('symbol-modal').addEventListener('click', function(e) {
            if (e.target === this) this.style.display = 'none';
        });

        // 输入框回车触发发送
        document.getElementById('input-box').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const text = this.value.trim();
                text ? sendText() : sendEnter();
            }
            // 监听删除键（Backspace）
            if (e.key === 'Backspace') {
                const text = this.value.trim();
                // 输入框为空时，触发PC端删除
                if (!text) {
                    e.preventDefault(); // 阻止手机端输入框的默认删除行为（无内容可删）
                    sendDelete(); // 调用删除接口
                }
            }
        });
    </script>
</body>
</html>
'''

# ------------ 原有接口部分 ------------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/send', methods=['POST'])
def send_text():
    global LAST_OPERATION
    data = request.get_json()
    text = data.get('text', '').strip()
    if text:
        # 记录文本类型操作
        LAST_OPERATION = {"type": "text", "content": text}
        replaced_text = apply_replace_rules(text)
        paste_text(replaced_text)
        print(f"原始文本：{text} → 替换后：{replaced_text}")
    return jsonify({"status": "success"})

@app.route('/send_enter', methods=['POST'])
def send_enter():
    global LAST_OPERATION
    # 记录回车类型操作
    LAST_OPERATION = {"type": "enter", "content": ""}
    pyautogui.press('enter')
    print("执行回车操作，已记录历史")
    return jsonify({"status": "success"})

@app.route('/undo', methods=['POST'])
def undo_last():
    global LAST_OPERATION
    if not LAST_OPERATION["type"]:
        return jsonify({"status": "failed", "msg": "无历史操作可撤销"})
    
    # 执行对应类型的撤销动作
    undo_last_operation()
    # 提取要恢复的内容（文本操作返回原文本，回车操作返回空）
    recover_content = LAST_OPERATION["content"]
    # 清空历史操作，防止重复撤销
    LAST_OPERATION = {"type": None, "content": ""}
    
    return jsonify({
        "status": "success",
        "content": recover_content
    })

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return local_ip

# 新增：生成终端二维码函数
def generate_cli_qrcode(url):
    """在命令行输出字符画二维码"""
    try:
        # 调用 qrcode 库的终端生成逻辑
        qr_main(['--factory', 'qrcode.terminal.SixteenColor', url])
    except Exception as e:
        # 降级方案：使用简单字符二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

if __name__ == '__main__':
    local_ip = get_local_ip()
    port = 5000
    access_url = f"http://{local_ip}:{port}"
    
    print(f"\n服务器已启动！")
    print(f"手机访问地址：{access_url}")
    print(f"已加载 {len(REPLACE_RULES)} 条替换规则")
    print(f"注意：手机和电脑需在同一局域网下\n")
    
    # 新增：生成并输出终端二维码
    print("扫码访问（手机摄像头扫描下方二维码）：")
    generate_cli_qrcode(access_url)
    print()
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
