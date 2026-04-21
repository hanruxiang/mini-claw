"""HTTP 请求日志 - 记录实际发送给 API 的请求体"""

import json
import logging

logger = logging.getLogger(__name__)


def setup_http_logging():
    """设置 httpx 客户端的日志"""
    import httpx

    # Monkey patch httpx.AsyncClient 来添加日志
    original_async_client_init = httpx.AsyncClient.__init__

    def patched_async_client_init(self, *args, **kwargs):
        # 调用原始初始化
        original_async_client_init(self, *args, **kwargs)

        # 添加请求和响应的事件钩子
        @self.event_hook("request")
        def log_request(request: httpx.Request):
            if "api.deepseek.com" in str(request.url) or "api.openai.com" in str(request.url):
                logger.info("=" * 60)
                logger.info("【实际 HTTP 请求】")
                logger.info(f"URL: {request.url}")
                logger.info(f"Method: {request.method}")
                # 只显示关键 headers
                headers = {k: v for k, v in request.headers.items() if k.lower() in ['content-type', 'authorization']}
                logger.info(f"Headers: {headers}")

                # 记录请求体
                if request.content:
                    try:
                        body_json = json.loads(request.content)
                        logger.info(f"Body:\n{json.dumps(body_json, ensure_ascii=False, indent=2)}")
                    except:
                        content = request.content.decode('utf-8', errors='ignore')
                        logger.info(f"Body (raw): {content[:2000]}")
                logger.info("=" * 60)

        @self.event_hook("response")
        def log_response(response: httpx.Response):
            if "api.deepseek.com" in str(response.url) or "api.openai.com" in str(response.url):
                logger.info("=" * 60)
                logger.info("【实际 HTTP 响应】")
                logger.info(f"Status: {response.status_code}")

                # 记录响应体
                try:
                    response_json = response.json()
                    logger.info(f"Body:\n{json.dumps(response_json, ensure_ascii=False, indent=2)}")
                except:
                    text = response.text
                    logger.info(f"Body (raw): {text[:2000]}")
                logger.info("=" * 60)

    httpx.AsyncClient.__init__ = patched_async_client_init
