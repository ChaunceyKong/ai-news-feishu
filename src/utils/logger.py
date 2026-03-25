"""
日志工具模块
"""

import logging
import json
import sys
from typing import Any, Dict
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON字符串"""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """文本格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为文本字符串"""
        # 基础格式：时间 级别 模块:消息
        message = super().format(record)

        # 添加额外字段
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            extra_str = " ".join([f"{k}={v}" for k, v in record.extra.items()])
            if extra_str:
                message = f"{message} [{extra_str}]"

        return message


def setup_logger(
    name: str = "ai_news_feishu",
    level: str = "INFO",
    format_type: str = "json",
    log_file: str = None,
) -> logging.Logger:
    """
    设置并返回配置好的日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 日志格式类型，支持 "json" 或 "text"
        log_file: 日志文件路径，如果为None则只输出到控制台

    Returns:
        配置好的日志记录器
    """
    # 获取日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 创建或获取日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 创建格式化器
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            logger.warning(f"无法创建日志文件 {log_file}: {e}")

    # 避免日志传播到根日志记录器
    logger.propagate = False

    return logger


# 全局日志记录器实例
_logger_instance: logging.Logger = None


def get_logger() -> logging.Logger:
    """获取全局日志记录器实例"""
    global _logger_instance

    if _logger_instance is None:
        # 从环境变量获取配置
        import os
        from ..config import get_config

        try:
            config = get_config()
            level = config.get_settings().get("log_level", "INFO")
            format_type = config.get_settings().get("log_format", "json")
        except Exception:
            # 如果配置未初始化，使用默认值
            level = os.getenv("LOG_LEVEL", "INFO")
            format_type = os.getenv("LOG_FORMAT", "json")

        _logger_instance = setup_logger(
            name="ai_news_feishu",
            level=level,
            format_type=format_type,
        )

    return _logger_instance