from flask import Flask, request, render_template_string, jsonify
import pyautogui
import pyperclip
import socket
import re
import os
import sys

app = Flask(__name__)

# 存储正则替换规则（key: 编译后的正则表达式，value: 替换式）
REPLACE_RULES = []

# ===== 重构历史记录：存储上一次操作的类型和内容 =====
# 格式: {"type": "text"/"enter", "content": 文本内容/空字符串}
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

# ===== 新增：方向键控制接口 =====
@app.route('/move_cursor', methods=['POST'])
def move_cursor():
    direction = request.json.get('direction')
    # 使用 pyautogui 模拟方向键按下
    if direction in ['left', 'up', 'down', 'right']:
        pyautogui.press(direction)
        print(f"执行光标移动：{direction}")
    return jsonify({"status": "success"})

# 网页前端模板（修复中文引号传参问题）
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>手机-电脑输入同步（支持符号包裹）</title>
    <style>
        body {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding-top: 50px;
            background-color: #f0f0f0;
        }
        #input-box {
            width: 90%;
            height: 150px;
            padding: 15px;
            font-size: 18px;
            border: 2px solid #4CAF50;
            border-radius: 8px;
            resize: none;
        }
        .btn-group {
            width: 90%;
            margin-top: 20px;
            display: flex;
            gap: 10px;
        }
        .func-btn {
            flex: 1;
            padding: 15px;
            font-size: 20px;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        #send-text-btn {
            background-color: #4CAF50;
        }
        #send-enter-btn {
            background-color: #2196F3;
        }
        #undo-btn {
            background-color: #9E9E9E; /* 默认灰色 */
        }
        #undo-btn.enabled {
            background-color: #4CAF50; /* 可点击时绿色 */
        }
        #clear-btn {
            background-color: #f44336; /* 红色区分清空功能 */
        }
        /* 方向按钮样式 */
        .dir-btn {
            flex: 1;
            padding: 15px;
            font-size: 20px;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            background-color: #607d8b; /* 灰色区分方向功能 */
        }
        /* 成对符号按钮样式 */
        .symbol-btn {
            flex: 1;
            padding: 15px;
            font-size: 20px;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            background-color: #9c27b0; /* 紫色区分符号功能 */
        }
        .func-btn:active, .dir-btn:active, .symbol-btn:active {
            opacity: 0.8;
        }
        /* 弹出输入框遮罩 */
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
        /* 弹出输入框容器 */
        .modal-content {
            width: 80%;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        #symbol-input {
            padding: 15px;
            font-size: 18px;
            border: 2px solid #4CAF50;
            border-radius: 8px;
        }
        #confirm-symbol {
            padding: 15px;
            font-size: 18px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <textarea id="input-box" placeholder="请输入内容（支持正则替换，规则在 hot-rule.txt 中配置）..."></textarea>
    <!-- 原有功能按钮组 -->
    <div class="btn-group">
        <button class="func-btn" id="send-text-btn" onclick="sendText()">发送文本</button>
        <button class="func-btn" id="send-enter-btn" onclick="sendEnter()">发送回车</button>
        <button class="func-btn" id="undo-btn" onclick="undoLast()" disabled>撤销</button>
        <button class="func-btn" id="clear-btn" onclick="clearInput()">清空文本</button>
    </div>
    <!-- 方向按钮组 -->
    <div class="btn-group">
        <button class="dir-btn" onclick="moveCursor('left')">左</button>
        <button class="dir-btn" onclick="moveCursor('up')">上</button>
        <button class="dir-btn" onclick="moveCursor('down')">下</button>
        <button class="dir-btn" onclick="moveCursor('right')">右</button>
    </div>
    <!-- 新增成对符号按钮组：修复中文引号传参 -->
    <div class="btn-group">
        <button class="symbol-btn" onclick="openSymbolModal('()')">（）</button>
        <button class="symbol-btn" onclick="openSymbolModal('“”')">“”</button>
        <button class="symbol-btn" onclick="openSymbolModal('「」')">「」</button>
        <button class="symbol-btn" onclick="openSymbolModal('[]')">[]</button>
    </div>

    <!-- 弹出输入框遮罩 -->
    <div id="symbol-modal">
        <div class="modal-content">
            <input type="text" id="symbol-input" placeholder="请输入要包裹的内容..." />
            <button id="confirm-symbol" onclick="confirmSymbol()">确认</button>
        </div>
    </div>

    <script>
        let hasHistory = false; // 标记是否有可撤销的历史操作
        let currentSymbol = ""; // 存储当前选中的成对符号

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
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({text: text})
            }).then(() => {
                hasHistory = true; // 文本操作标记为可撤销
                updateUndoBtn();
                document.getElementById('input-box').value = '';
            });
        }

        function sendEnter() {
            fetch('/send_enter', {
                method: 'POST'
            }).then(() => {
                hasHistory = true; // 回车操作也标记为可撤销
                updateUndoBtn();
            });
        }

        function undoLast() {
            fetch('/undo', {
                method: 'POST'
            }).then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 恢复文本内容（仅文本操作有内容，回车操作返回空）
                    document.getElementById('input-box').value = data.content || '';
                    hasHistory = false; // 撤销后清空历史
                    updateUndoBtn();
                }
            });
        }

        function clearInput() {
            // 仅清空手机端文本框，不调用任何后端接口，不影响PC端
            document.getElementById('input-box').value = '';
        }

        function moveCursor(direction) {
            fetch('/move_cursor', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({direction: direction})
            }).then(() => {
                // 移动光标后禁用撤销按钮
                hasHistory = false;
                updateUndoBtn();
            });
        }

        // ===== 新增：打开符号输入弹窗 =====
        function openSymbolModal(symbol) {
            currentSymbol = symbol;
            const modal = document.getElementById('symbol-modal');
            const input = document.getElementById('symbol-input');
            // 清空输入框并显示弹窗
            input.value = '';
            modal.style.display = 'flex';
            // 聚焦输入框，弹出输入法
            setTimeout(() => input.focus(), 100);
        }

        // ===== 新增：在光标位置插入包裹后的内容 =====
        function insertAtCursor(text) {
            const input = document.getElementById('input-box');
            const startPos = input.selectionStart;
            const endPos = input.selectionEnd;
            const value = input.value;
            // 插入内容到光标位置
            input.value = value.substring(0, startPos) + text + value.substring(endPos);
            // 恢复光标位置到插入内容的末尾
            input.selectionStart = input.selectionEnd = startPos + text.length;
            // 聚焦主输入框
            input.focus();
        }

        // ===== 新增：确认符号包裹并插入 =====
        function confirmSymbol() {
            const input = document.getElementById('symbol-input');
            const content = input.value.trim();
            if (!content) {
                // 无内容时直接关闭弹窗
                document.getElementById('symbol-modal').style.display = 'none';
                return;
            }
            // 拆分成对符号（前半部分和后半部分）
            const leftSymbol = currentSymbol.substring(0, currentSymbol.length / 2);
            const rightSymbol = currentSymbol.substring(currentSymbol.length / 2);
            // 包裹内容
            const wrappedText = leftSymbol + content + rightSymbol;
            // 插入到主输入框光标位置
            insertAtCursor(wrappedText);
            // 关闭弹窗
            document.getElementById('symbol-modal').style.display = 'none';
        }

        // ===== 新增：输入框回车触发确认 =====
        document.getElementById('symbol-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmSymbol();
            }
        });

        // 点击遮罩关闭弹窗
        document.getElementById('symbol-modal').addEventListener('click', function(e) {
            if (e.target === this) {
                this.style.display = 'none';
            }
        });

        // 回车事件监听逻辑：区分文本有无执行对应操作
        document.getElementById('input-box').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const text = this.value.trim();
                if (text) {
                    sendText();
                } else {
                    sendEnter();
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

if __name__ == '__main__':
    local_ip = get_local_ip()
    port = 5000
    print(f"\n服务器已启动！")
    print(f"手机访问地址：http://{local_ip}:{port}")
    print(f"已加载 {len(REPLACE_RULES)} 条替换规则")
    print(f"注意：手机和电脑需在同一局域网下\n")
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
