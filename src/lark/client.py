"""
飞书API客户端模块
"""

import logging
import time
from typing import Dict, Any, Optional, List, Union
import requests
from ..utils.retry_manager import api_retry
from ..utils.logger import get_logger

logger = get_logger()


class LarkClient:
    """
    飞书API客户端，封装飞书开放平台API调用
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn/open-apis",
        timeout: int = 10,
    ):
        """
        初始化飞书客户端

        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            base_url: API基础地址
            timeout: 请求超时时间（秒）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # 认证信息缓存
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0

        # HTTP会话
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AI-News-Feishu-Bot/1.0",
        })

    def _ensure_token_valid(self) -> None:
        """确保租户访问令牌有效，如果无效则重新获取"""
        current_time = time.time()

        # 如果令牌不存在或已过期（预留30秒缓冲），则重新获取
        if not self._tenant_access_token or current_time >= self._token_expire_time - 30:
            self._refresh_tenant_access_token()

    @api_retry.as_decorator()
    def _refresh_tenant_access_token(self) -> None:
        """获取租户访问令牌"""
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"

        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        try:
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()

            if result.get("code") != 0:
                error_msg = result.get("msg", "未知错误")
                logger.error(f"获取租户访问令牌失败: {error_msg}")
                raise ValueError(f"飞书API错误: {error_msg}")

            token_data = result.get("tenant_access_token", "")
            expire_time = result.get("expire", 7200)  # 默认7200秒

            self._tenant_access_token = token_data
            self._token_expire_time = time.time() + expire_time

            logger.info("成功获取租户访问令牌")

        except requests.exceptions.RequestException as e:
            logger.error(f"请求飞书API失败: {e}")
            raise
        except ValueError as e:
            logger.error(f"飞书API返回数据解析失败: {e}")
            raise

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        发送HTTP请求到飞书API（内部方法）

        Args:
            method: HTTP方法 (GET, POST, PUT, DELETE)
            endpoint: API端点（不包含基础URL）
            data: 请求体数据
            params: 查询参数
            headers: 额外请求头

        Returns:
            API响应数据

        Raises:
            ValueError: API返回错误码
            requests.exceptions.RequestException: 网络请求失败
        """
        self._ensure_token_valid()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # 构建请求头
        request_headers = {
            "Authorization": f"Bearer {self._tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        if headers:
            request_headers.update(headers)

        # 发送请求
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=self.timeout,
            )

            # 检查HTTP状态码
            response.raise_for_status()

            # 解析响应
            result = response.json()

            # 检查飞书API错误码
            api_code = result.get("code")
            if api_code != 0:
                error_msg = result.get("msg", "未知错误")
                logger.error(f"飞书API错误: code={api_code}, msg={error_msg}")

                # 特定错误码处理
                if api_code == 99991663:  # 租户访问令牌过期
                    logger.warning("租户访问令牌过期，尝试刷新")
                    self._refresh_tenant_access_token()
                    # 可以在这里实现自动重试，但为了避免递归，调用者需要处理

                raise ValueError(f"飞书API错误: {error_msg} (code={api_code})")

            return result.get("data", {})

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"

            # 限流处理（429状态码）
            if status_code == 429:
                logger.warning("飞书API限流，等待后重试")
                # 返回特定错误，让调用者处理重试
                raise ValueError("API限流，请稍后重试")

            logger.error(f"HTTP请求失败: status={status_code}, error={e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            raise
        except ValueError as e:
            logger.error(f"响应解析失败: {e}")
            raise

    @api_retry.as_decorator()
    def send_message(
        self,
        receiver_id: str,
        message_type: str,
        content: Union[str, Dict],
        receiver_type: str = "chat",
    ) -> Dict[str, Any]:
        """
        发送消息到飞书

        Args:
            receiver_id: 接收者ID，群聊ID或用户open_id
            message_type: 消息类型，支持 "text", "post", "image", "interactive" 等
            content: 消息内容，字符串或字典
            receiver_type: 接收者类型，"chat"（群聊）或 "user"（用户）

        Returns:
            发送结果
        """
        endpoint = "im/v1/messages"
        params = {"receive_id_type": receiver_type}

        # 构建消息体
        if isinstance(content, str):
            content_data = {"text": content}
        else:
            content_data = content

        data = {
            "receive_id": receiver_id,
            "msg_type": message_type,
            "content": content_data,
        }

        try:
            result = self._make_request("POST", endpoint, data=data, params=params)
            logger.info(f"成功发送消息到 {receiver_type} {receiver_id}")
            return result
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            raise

    @api_retry.as_decorator()
    def send_text_message(self, receiver_id: str, text: str, receiver_type: str = "chat") -> Dict[str, Any]:
        """
        发送文本消息

        Args:
            receiver_id: 接收者ID
            text: 文本内容
            receiver_type: 接收者类型

        Returns:
            发送结果
        """
        # 飞书文本消息格式
        content = json.dumps({"text": text}, ensure_ascii=False)
        return self.send_message(receiver_id, "text", content, receiver_type)

    @api_retry.as_decorator()
    def send_interactive_message(
        self, receiver_id: str, card_content: Dict, receiver_type: str = "chat"
    ) -> Dict[str, Any]:
        """
        发送交互式消息卡片

        Args:
            receiver_id: 接收者ID
            card_content: 卡片内容，符合飞书卡片格式
            receiver_type: 接收者类型

        Returns:
            发送结果
        """
        content = json.dumps(card_content, ensure_ascii=False)
        return self.send_message(receiver_id, "interactive", content, receiver_type)

    @api_retry.as_decorator()
    def batch_send_messages(
        self,
        receiver_ids: List[str],
        message_type: str,
        content: Union[str, Dict],
        receiver_type: str = "chat",
        batch_size: int = 5,
        delay_between_batches: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        批量发送消息，自动处理限流

        Args:
            receiver_ids: 接收者ID列表
            message_type: 消息类型
            content: 消息内容
            receiver_type: 接收者类型
            batch_size: 每批发送数量
            delay_between_batches: 批次间延迟（秒）

        Returns:
            发送结果列表
        """
        results = []

        for i in range(0, len(receiver_ids), batch_size):
            batch = receiver_ids[i:i + batch_size]
            batch_results = []

            for receiver_id in batch:
                try:
                    result = self.send_message(
                        receiver_id, message_type, content, receiver_type
                    )
                    batch_results.append({
                        "receiver_id": receiver_id,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"发送消息到 {receiver_id} 失败: {e}")
                    batch_results.append({
                        "receiver_id": receiver_id,
                        "success": False,
                        "error": str(e),
                    })

            results.extend(batch_results)

            # 如果不是最后一批，等待延迟
            if i + batch_size < len(receiver_ids):
                logger.debug(f"等待 {delay_between_batches} 秒后发送下一批消息")
                time.sleep(delay_between_batches)

        return results

    def test_connection(self) -> bool:
        """
        测试飞书API连接

        Returns:
            连接是否成功
        """
        try:
            self._refresh_tenant_access_token()
            logger.info("飞书API连接测试成功")
            return True
        except Exception as e:
            logger.error(f"飞书API连接测试失败: {e}")
            return False


# 导入json模块（在文件顶部已定义，但需要在此处添加）
import json