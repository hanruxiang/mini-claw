#!/usr/bin/env python3
"""DeepSeek API 代理 - 用于查看实际的请求和响应"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 从环境变量或 config.yaml 读取 API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    # 尝试从 config.yaml 读取
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
            DEEPSEEK_API_KEY = config.get("models", {}).get("providers", {}).get("deepseek", {}).get("api_key", "")
            # 替换环境变量占位符
            if DEEPSEEK_API_KEY.startswith("${") and DEEPSEEK_API_KEY.endswith("}"):
                env_var = DEEPSEEK_API_KEY[2:-1]
                DEEPSEEK_API_KEY = os.environ.get(env_var, "")

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 日志目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    """代理所有请求到 DeepSeek API"""
    # 构建目标 URL - 添加 /v1 前缀
    target_url = f"{DEEPSEEK_BASE_URL}/v1/{path}"

    # 如果有查询参数，添加到 URL
    if request.args:
        target_url += f"?{request.query_string.decode()}"

    # 获取请求体
    req_body = None
    if request.data:
        try:
            req_body = request.get_json()
        except:
            pass

    # 构建请求头
    headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']}
    headers['Authorization'] = f"Bearer {DEEPSEEK_API_KEY}"

    try:
        # 发送请求到 DeepSeek API
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            json=req_body,
            timeout=120
        )

        # 记录请求和响应
        print("=" * 60)
        print(f"【请求】{request.method} {target_url}")
        if req_body:
            print(f"Body:\n{json.dumps(req_body, ensure_ascii=False, indent=2)}")

        print(f"\n【响应】状态码: {resp.status_code}")
        try:
            resp_json = resp.json()
            print(f"Body:\n{json.dumps(resp_json, ensure_ascii=False, indent=2)}")
        except:
            print(f"Body: {resp.text[:500]}")
        print("=" * 60)

        # 返回响应
        return Response(
            resp.content,
            status=resp.status_code,
            headers=dict(resp.headers)
        )

    except Exception as e:
        print(f"错误: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not DEEPSEEK_API_KEY:
        print("❌ 错误: 请设置 DEEPSEEK_API_KEY 环境变量")
        exit(1)

    print("🚀 DeepSeek API 代理启动...")
    print(f"🌐 代理地址: http://localhost:8000")
    print(f"🎯 目标: {DEEPSEEK_BASE_URL}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app.run(host="127.0.0.1", port=8000, debug=False)
