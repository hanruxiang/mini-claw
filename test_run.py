#!/usr/bin/env python3
"""测试主程序是否能正常工作"""

import subprocess
import sys
import time

# 启动主程序
proc = subprocess.Popen(
    [sys.executable, "main.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,  # 行缓冲
)

# 等待程序启动
time.sleep(1)

# 发送输入
try:
    # 发送"你好"
    proc.stdin.write("你好\n")
    proc.stdin.flush()

    # 等待响应
    time.sleep(5)

    # 发送退出命令
    proc.stdin.write("/exit\n")
    proc.stdin.flush()

    # 获取输出
    stdout, stderr = proc.communicate(timeout=5)

    print("=== STDOUT ===")
    print(stdout)
    print("\n=== STDERR ===")
    print(stderr)

except subprocess.TimeoutExpired:
    proc.kill()
    print("程序超时！")
except Exception as e:
    proc.kill()
    print(f"错误: {e}")
