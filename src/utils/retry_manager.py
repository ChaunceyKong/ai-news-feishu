"""
重试管理器模块
"""

import time
import logging
from typing import Callable, Any, Optional, Type, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


class RetryManager:
    """
    重试管理器，支持指数退避和自定义重试条件
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        retry_conditions: Optional[Callable[[Any], bool]] = None,
    ):
        """
        初始化重试管理器

        Args:
            max_retries: 最大重试次数（不包括第一次尝试）
            base_delay: 基础延迟时间（秒），用于指数退避计算
            max_delay: 最大延迟时间（秒）
            retry_exceptions: 需要重试的异常类型元组
            retry_conditions: 自定义重试条件函数，接受返回值为参数，返回bool
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_exceptions = retry_exceptions
        self.retry_conditions = retry_conditions

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行函数并自动重试

        Args:
            func: 要执行的函数
            *args: 函数位置参数
            **kwargs: 函数关键字参数

        Returns:
            函数的返回值

        Raises:
            Exception: 当达到最大重试次数后仍然失败时抛出异常
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 包括第一次尝试
            try:
                result = func(*args, **kwargs)

                # 检查是否需要根据返回值重试
                if self.retry_conditions and self.retry_conditions(result):
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            f"函数 {func.__name__} 返回值触发重试条件，"
                            f"第 {attempt + 1} 次尝试，等待 {delay:.1f} 秒后重试"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"函数 {func.__name__} 达到最大重试次数，返回值仍不满足条件"
                        )
                        raise ValueError("达到最大重试次数，返回值仍不满足条件")

                # 成功执行，返回结果
                if attempt > 0:
                    logger.info(f"函数 {func.__name__} 在第 {attempt + 1} 次尝试成功")

                return result

            except self.retry_exceptions as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"函数 {func.__name__} 执行失败，"
                        f"第 {attempt + 1} 次尝试，错误: {str(e)}，"
                        f"等待 {delay:.1f} 秒后重试"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"函数 {func.__name__} 达到最大重试次数，最终失败，错误: {str(e)}"
                    )

        # 所有重试都失败，抛出最后一个异常
        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """
        计算重试延迟时间（指数退避）

        Args:
            attempt: 当前尝试次数（0-based）

        Returns:
            延迟时间（秒）
        """
        delay = self.base_delay * (2 ** attempt)  # 指数退避
        delay = min(delay, self.max_delay)  # 不超过最大延迟
        return delay

    def as_decorator(self):
        """
        将重试管理器转换为装饰器

        Returns:
            装饰器函数
        """

        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self.execute_with_retry(func, *args, **kwargs)

            return wrapper

        return decorator


# 预定义的重试管理器实例

# 网络请求重试（针对连接错误和超时）
network_retry = RetryManager(
    max_retries=3,
    base_delay=1.0,
    max_delay=10.0,
    retry_exceptions=(ConnectionError, TimeoutError),
)

# API调用重试（针对服务端错误和限流）
api_retry = RetryManager(
    max_retries=3,
    base_delay=2.0,
    max_delay=30.0,
    retry_exceptions=(Exception,),  # 更广泛的异常捕获
)


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    重试装饰器工厂函数

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        retry_exceptions: 需要重试的异常类型

    Returns:
        重试装饰器
    """

    def decorator(func: Callable):
        retry_manager = RetryManager(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            retry_exceptions=retry_exceptions,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_manager.execute_with_retry(func, *args, **kwargs)

        return wrapper

    return decorator