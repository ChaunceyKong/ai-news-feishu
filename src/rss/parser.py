"""
RSS解析模块
"""

import re
from typing import List, Dict, Any
from datetime import datetime
from .models import Article
from ..utils.logger import get_logger

logger = get_logger()


class RSSParser:
    """
    RSS解析器，提供高级解析功能
    """

    @staticmethod
    def filter_articles(
        articles: List[Article],
        min_title_length: int = 5,
        exclude_keywords: List[str] = None,
        include_keywords: List[str] = None,
    ) -> List[Article]:
        """
        过滤文章列表

        Args:
            articles: 文章列表
            min_title_length: 最小标题长度
            exclude_keywords: 排除关键词列表
            include_keywords: 包含关键词列表（如果提供，只保留包含这些关键词的文章）

        Returns:
            过滤后的文章列表
        """
        if not articles:
            return []

        filtered_articles = []

        for article in articles:
            title = article.title.lower()
            summary = article.summary.lower()

            # 检查标题长度
            if len(article.title) < min_title_length:
                logger.debug(f"文章标题过短被过滤: {article.title}")
                continue

            # 排除关键词
            if exclude_keywords:
                should_exclude = False
                for keyword in exclude_keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in title or keyword_lower in summary:
                        logger.debug(f"文章包含排除关键词被过滤: {article.title}")
                        should_exclude = True
                        break
                if should_exclude:
                    continue

            # 包含关键词（如果提供）
            if include_keywords:
                should_include = False
                for keyword in include_keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in title or keyword_lower in summary:
                        should_include = True
                        break
                if not should_include:
                    logger.debug(f"文章不包含关键词被过滤: {article.title}")
                    continue

            filtered_articles.append(article)

        logger.info(f"文章过滤: {len(articles)} -> {len(filtered_articles)}")
        return filtered_articles

    @staticmethod
    def sort_articles(
        articles: List[Article],
        sort_by: str = "published",
        descending: bool = True,
    ) -> List[Article]:
        """
        排序文章列表

        Args:
            articles: 文章列表
            sort_by: 排序字段，支持 "published", "title", "source"
            descending: 是否降序排列

        Returns:
            排序后的文章列表
        """
        if not articles:
            return []

        def get_sort_key(article: Article):
            if sort_by == "published":
                # 尝试解析发布时间
                try:
                    return RSSParser._parse_datetime(article.published)
                except:
                    return datetime.min
            elif sort_by == "title":
                return article.title.lower()
            elif sort_by == "source":
                return article.source.lower()
            else:
                return article.hash

        sorted_articles = sorted(
            articles,
            key=get_sort_key,
            reverse=descending,
        )

        return sorted_articles

    @staticmethod
    def group_articles_by_category(articles: List[Article]) -> Dict[str, List[Article]]:
        """
        按分类分组文章

        Args:
            articles: 文章列表

        Returns:
            按分类分组的文章字典
        """
        grouped = {}

        for article in articles:
            category = article.category
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(article)

        return grouped

    @staticmethod
    def group_articles_by_source(articles: List[Article]) -> Dict[str, List[Article]]:
        """
        按来源分组文章

        Args:
            articles: 文章列表

        Returns:
            按来源分组的文章字典
        """
        grouped = {}

        for article in articles:
            source = article.source
            if source not in grouped:
                grouped[source] = []
            grouped[source].append(article)

        return grouped

    @staticmethod
    def remove_duplicates(articles: List[Article]) -> List[Article]:
        """
        去除重复文章（基于哈希值）

        Args:
            articles: 文章列表

        Returns:
            去重后的文章列表
        """
        if not articles:
            return []

        seen_hashes = set()
        unique_articles = []

        for article in articles:
            if article.hash not in seen_hashes:
                seen_hashes.add(article.hash)
                unique_articles.append(article)
            else:
                logger.debug(f"发现重复文章: {article.title}")

        logger.info(f"文章去重: {len(articles)} -> {len(unique_articles)}")
        return unique_articles

    @staticmethod
    def _parse_datetime(datetime_str: str) -> datetime:
        """
        解析日期时间字符串

        Args:
            datetime_str: 日期时间字符串

        Returns:
            日期时间对象

        Raises:
            ValueError: 解析失败
        """
        if not datetime_str:
            raise ValueError("日期时间字符串为空")

        # 常见日期时间格式
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RSS标准格式
            "%a, %d %b %Y %H:%M:%S %Z",  # 有时区名称
            "%Y-%m-%dT%H:%M:%SZ",  # ISO格式
            "%Y-%m-%dT%H:%M:%S%z",  # ISO带时区
            "%Y-%m-%d %H:%M:%S",  # 简单格式
            "%Y/%m/%d %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue

        # 如果所有格式都失败，尝试更灵活的解析
        try:
            # 移除时区信息
            dt_str_clean = re.sub(r'\s*[A-Z]{3,4}$', '', datetime_str)
            dt_str_clean = re.sub(r'\s*[+-]\d{4}$', '', dt_str_clean)

            for fmt in ["%a, %d %b %Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(dt_str_clean, fmt)
                except ValueError:
                    continue
        except Exception:
            pass

        raise ValueError(f"无法解析日期时间字符串: {datetime_str}")

    @staticmethod
    def extract_keywords(
        articles: List[Article],
        top_n: int = 10,
        min_word_length: int = 3,
    ) -> List[str]:
        """
        从文章标题中提取关键词

        Args:
            articles: 文章列表
            top_n: 返回前N个关键词
            min_word_length: 最小单词长度

        Returns:
            关键词列表
        """
        if not articles:
            return []

        from collections import Counter
        import re

        # 停用词列表
        stop_words = {
            "the", "and", "for", "with", "from", "this", "that", "are", "was", "were",
            "has", "have", "had", "will", "would", "can", "could", "should", "about",
            "using", "based", "through", "according", "research", "study", "new",
            "的", "和", "与", "在", "是", "了", "有", "对", "中", "为", "等", "基于",
        }

        word_counter = Counter()

        for article in articles:
            title = article.title.lower()

            # 分割单词
            words = re.findall(r'\b[a-z]{3,}\b', title)  # 只匹配英文单词

            # 过滤停用词
            filtered_words = [w for w in words if w not in stop_words]

            # 更新计数器
            word_counter.update(filtered_words)

        # 获取最常见的关键词
        keywords = [word for word, count in word_counter.most_common(top_n)]

        return keywords