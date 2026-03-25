"""
内容处理模块
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from .rss.models import Article
from .rss.parser import RSSParser
from .lark.message_builder import MessageBuilder
from .storage.database import get_storage
from .utils.logger import get_logger

logger = get_logger()


class ContentProcessor:
    """
    内容处理器，负责文章处理、消息构建和发送准备
    """

    def __init__(self, config=None):
        """
        初始化内容处理器

        Args:
            config: 配置对象
        """
        self.config = config
        self.storage = get_storage()
        self.message_builder = MessageBuilder()

    def process_articles(
        self,
        articles: List[Article],
        filter_duplicates: bool = True,
        filter_options: Optional[Dict[str, Any]] = None,
        sort_options: Optional[Dict[str, Any]] = None,
    ) -> List[Article]:
        """
        处理文章列表

        Args:
            articles: 原始文章列表
            filter_duplicates: 是否过滤重复文章
            filter_options: 过滤选项
            sort_options: 排序选项

        Returns:
            处理后的文章列表
        """
        if not articles:
            return []

        logger.info(f"开始处理 {len(articles)} 篇文章")

        # 1. 过滤重复文章（基于数据库）
        if filter_duplicates:
            articles = self.storage.filter_new_articles(articles)
            if not articles:
                logger.info("所有文章都已处理过，没有新文章")
                return []

        # 2. 应用自定义过滤
        if filter_options:
            articles = self._apply_filters(articles, filter_options)

        # 3. 排序
        if sort_options:
            articles = self._apply_sorting(articles, sort_options)
        else:
            # 默认按发布时间降序排序
            articles = RSSParser.sort_articles(articles, sort_by="published", descending=True)

        logger.info(f"处理后剩余 {len(articles)} 篇文章")
        return articles

    def _apply_filters(self, articles: List[Article], filter_options: Dict[str, Any]) -> List[Article]:
        """应用过滤选项"""
        exclude_keywords = filter_options.get("exclude_keywords", [])
        include_keywords = filter_options.get("include_keywords", [])
        min_title_length = filter_options.get("min_title_length", 5)

        return RSSParser.filter_articles(
            articles,
            min_title_length=min_title_length,
            exclude_keywords=exclude_keywords,
            include_keywords=include_keywords,
        )

    def _apply_sorting(self, articles: List[Article], sort_options: Dict[str, Any]) -> List[Article]:
        """应用排序选项"""
        sort_by = sort_options.get("sort_by", "published")
        descending = sort_options.get("descending", True)

        return RSSParser.sort_articles(articles, sort_by=sort_by, descending=descending)

    def build_messages(
        self,
        articles: List[Article],
        message_type: str = "mixed",
        max_text_articles: int = 3,
        include_digest: bool = True,
    ) -> Dict[str, Any]:
        """
        构建消息

        Args:
            articles: 文章列表
            message_type: 消息类型，支持 "text", "card", "mixed"
            max_text_articles: 文本消息中显示的最大文章数
            include_digest: 是否包含摘要卡片

        Returns:
            消息字典
        """
        if not articles:
            return {"text_message": None, "card_messages": []}

        logger.info(f"为 {len(articles)} 篇文章构建 {message_type} 类型消息")

        if message_type == "text":
            # 纯文本消息
            text_message = self._build_text_summary(articles, max_text_articles)
            return {"text_message": text_message, "card_messages": []}

        elif message_type == "card":
            # 纯卡片消息
            if len(articles) <= 5:
                # 文章较少时，每篇文章一个卡片
                card_messages = []
                for article in articles:
                    card = self.message_builder.build_article_card(
                        title=article.title,
                        link=article.link,
                        summary=article.summary,
                        source=article.source,
                        publish_time=article.published,
                        category=article.category,
                        language=article.language,
                    )
                    card_messages.append(card)
            else:
                # 文章较多时，使用摘要卡片
                articles_dicts = [article.to_dict() for article in articles]
                card = self.message_builder.build_daily_digest_card(articles_dicts)
                card_messages = [card]

            return {"text_message": None, "card_messages": card_messages}

        else:  # mixed
            # 混合消息（文本摘要 + 卡片）
            articles_dicts = [article.to_dict() for article in articles]
            mixed_result = self.message_builder.build_mixed_message(
                articles_dicts,
                max_text_articles=max_text_articles,
                include_digest=include_digest,
            )
            return mixed_result

    def _build_text_summary(self, articles: List[Article], max_articles: int = 3) -> str:
        """构建文本摘要"""
        lines = ["📰 AI资讯摘要"]
        lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        for i, article in enumerate(articles[:max_articles]):
            display_title = article.get_display_title(60)
            lines.append(f"{i+1}. {display_title}")
            lines.append(f"   来源: {article.source}")
            lines.append(f"   链接: {article.link}")
            lines.append("")

        if len(articles) > max_articles:
            lines.append(f"... 还有 {len(articles) - max_articles} 篇文章")

        return "\n".join(lines)

    def mark_articles_processed(self, articles: List[Article]) -> int:
        """
        标记文章为已处理

        Args:
            articles: 文章列表

        Returns:
            成功标记的数量
        """
        if not articles:
            return 0

        count = self.storage.batch_mark_processed(articles)
        logger.info(f"成功标记 {count} 篇文章为已处理")
        return count

    def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计"""
        stats = self.storage.get_processed_stats(days=7)

        # 添加今日统计
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = stats.get("daily_stats", {}).get(today, 0)

        stats["today_count"] = today_count
        return stats

    def generate_report(self, articles: List[Article]) -> Dict[str, Any]:
        """
        生成处理报告

        Args:
            articles: 处理的文章列表

        Returns:
            报告字典
        """
        if not articles:
            return {"total": 0, "by_source": {}, "by_category": {}}

        # 按来源分组
        by_source = {}
        by_category = {}

        for article in articles:
            # 来源统计
            source = article.source
            by_source[source] = by_source.get(source, 0) + 1

            # 分类统计
            category = article.category
            by_category[category] = by_category.get(category, 0) + 1

        # 关键词提取
        keywords = RSSParser.extract_keywords(articles, top_n=5)

        return {
            "total": len(articles),
            "by_source": by_source,
            "by_category": by_category,
            "top_keywords": keywords,
            "processing_time": datetime.now().isoformat(),
        }