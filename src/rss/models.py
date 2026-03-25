"""
RSS数据模型模块
"""

import hashlib
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from ..utils.logger import get_logger

logger = get_logger()


@dataclass
class Article:
    """
    文章数据模型
    """

    # 核心字段
    title: str
    link: str
    source: str  # RSS源名称

    # 可选字段
    summary: str = ""
    published: str = ""
    category: str = "AI"
    language: str = "en"

    # 计算字段
    hash: str = field(init=False)  # 去重哈希值
    processed_at: Optional[datetime] = None

    def __post_init__(self):
        """初始化后计算哈希值"""
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        """
        计算文章哈希值（用于去重）

        Returns:
            MD5哈希字符串
        """
        # 使用标题和链接计算哈希（如果链接相同，基本可以确定是同一篇文章）
        content = f"{self.link}|{self.title}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """
        转换为字典

        Returns:
            文章字典
        """
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "summary": self.summary,
            "published": self.published,
            "category": self.category,
            "language": self.language,
            "hash": self.hash,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """
        从字典创建文章实例

        Args:
            data: 文章字典

        Returns:
            文章实例
        """
        article = cls(
            title=data.get("title", ""),
            link=data.get("link", ""),
            source=data.get("source", ""),
            summary=data.get("summary", ""),
            published=data.get("published", ""),
            category=data.get("category", "AI"),
            language=data.get("language", "en"),
        )

        # 设置处理时间
        if "processed_at" in data and data["processed_at"]:
            try:
                article.processed_at = datetime.fromisoformat(data["processed_at"])
            except (ValueError, TypeError):
                pass

        return article

    def is_valid(self) -> bool:
        """
        验证文章是否有效

        Returns:
            是否有效
        """
        if not self.title or not self.link:
            return False

        # 检查链接是否有效（简单检查）
        if not (self.link.startswith("http://") or self.link.startswith("https://")):
            logger.warning(f"文章链接无效: {self.link}")
            return False

        return True

    def get_display_title(self, max_length: int = 100) -> str:
        """
        获取显示用标题（自动截断）

        Args:
            max_length: 最大长度

        Returns:
            显示标题
        """
        if len(self.title) <= max_length:
            return self.title
        return self.title[:max_length] + "..."

    def get_display_summary(self, max_length: int = 200) -> str:
        """
        获取显示用摘要（自动截断）

        Args:
            max_length: 最大长度

        Returns:
            显示摘要
        """
        if not self.summary:
            return ""

        # 清理HTML标签（简单处理）
        import re
        clean_summary = re.sub(r'<[^>]+>', '', self.summary)

        if len(clean_summary) <= max_length:
            return clean_summary
        return clean_summary[:max_length] + "..."


@dataclass
class RSSSource:
    """
    RSS源配置模型
    """

    name: str
    url: str
    enabled: bool = True
    category: str = "AI"
    language: str = "en"
    max_articles: int = 10
    description: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "category": self.category,
            "language": self.language,
            "max_articles": self.max_articles,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RSSSource":
        """从字典创建实例"""
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=data.get("enabled", True),
            category=data.get("category", "AI"),
            language=data.get("language", "en"),
            max_articles=data.get("max_articles", 10),
            description=data.get("description", ""),
        )

    def is_valid(self) -> bool:
        """验证RSS源是否有效"""
        if not self.name or not self.url:
            return False

        if not (self.url.startswith("http://") or self.url.startswith("https://")):
            return False

        return True