"""
RSS抓取模块
"""

import time
from typing import List, Optional, Dict, Any
import feedparser
import requests
from ..utils.retry_manager import network_retry
from ..utils.logger import get_logger
from .models import Article, RSSSource

logger = get_logger()


class RSSFetcher:
    """
    RSS抓取器，负责从RSS源获取内容
    """

    def __init__(
        self,
        timeout: int = 10,
        user_agent: str = "AI-News-Feishu-Bot/1.0",
        enable_cache: bool = True,
        cache_ttl: int = 300,  # 5分钟
    ):
        """
        初始化RSS抓取器

        Args:
            timeout: 请求超时时间（秒）
            user_agent: User-Agent字符串
            enable_cache: 是否启用缓存
            cache_ttl: 缓存存活时间（秒）
        """
        self.timeout = timeout
        self.user_agent = user_agent
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl

        # 简单内存缓存
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}

        # HTTP会话
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def _get_from_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取RSS内容

        Args:
            url: RSS源URL

        Returns:
            缓存的RSS内容，如果不存在或已过期则返回None
        """
        if not self.enable_cache:
            return None

        if url in self._cache:
            cache_time = self._cache_timestamps.get(url, 0)
            if time.time() - cache_time < self.cache_ttl:
                logger.debug(f"从缓存获取RSS内容: {url}")
                return self._cache[url]

        return None

    def _save_to_cache(self, url: str, content: Dict[str, Any]) -> None:
        """
        保存RSS内容到缓存

        Args:
            url: RSS源URL
            content: RSS内容
        """
        if not self.enable_cache:
            return

        self._cache[url] = content
        self._cache_timestamps[url] = time.time()
        logger.debug(f"保存RSS内容到缓存: {url}")

    @network_retry.as_decorator()
    def fetch_feed(self, url: str, source_name: str = "") -> Dict[str, Any]:
        """
        获取RSS源内容

        Args:
            url: RSS源URL
            source_name: 源名称（用于日志）

        Returns:
            RSS解析结果字典

        Raises:
            ValueError: RSS获取或解析失败
        """
        # 检查缓存
        cached = self._get_from_cache(url)
        if cached:
            return cached

        logger.info(f"开始获取RSS源: {source_name or url}")

        try:
            # 使用feedparser解析RSS
            feed = feedparser.parse(url)

            # 检查解析结果
            if feed.bozo:  # bozo标志表示解析有问题
                bozo_exception = feed.bozo_exception
                logger.warning(f"RSS解析警告 {url}: {bozo_exception}")

            # 检查HTTP状态
            status = feed.get("status", 200)
            if status != 200:
                logger.warning(f"RSS返回非200状态码 {url}: {status}")

            result = {
                "url": url,
                "source_name": source_name,
                "feed": feed,
                "entries": feed.entries,
                "status": status,
                "bozo": feed.bozo,
                "bozo_exception": str(feed.bozo_exception) if feed.bozo_exception else None,
                "title": feed.feed.get("title", ""),
                "description": feed.feed.get("description", ""),
                "updated": feed.feed.get("updated", ""),
            }

            # 保存到缓存
            self._save_to_cache(url, result)

            logger.info(f"成功获取RSS源 {source_name or url}: {len(feed.entries)} 篇文章")
            return result

        except Exception as e:
            logger.error(f"获取RSS源失败 {url}: {e}")
            raise ValueError(f"获取RSS源失败: {e}")

    def fetch_source(self, source: RSSSource) -> List[Article]:
        """
        从单个RSS源获取文章

        Args:
            source: RSS源配置

        Returns:
            文章列表
        """
        if not source.enabled:
            logger.debug(f"RSS源已禁用: {source.name}")
            return []

        if not source.is_valid():
            logger.warning(f"RSS源配置无效: {source.name}")
            return []

        try:
            # 获取RSS内容
            feed_result = self.fetch_feed(source.url, source.name)

            # 解析文章
            articles = []
            entries = feed_result.get("entries", [])

            for i, entry in enumerate(entries[:source.max_articles]):
                try:
                    article = self._parse_entry(entry, source)
                    if article and article.is_valid():
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"解析文章失败 {source.name} 第{i+1}篇: {e}")

            logger.info(f"从 {source.name} 解析到 {len(articles)} 篇文章")
            return articles

        except Exception as e:
            logger.error(f"处理RSS源失败 {source.name}: {e}")
            return []

    def fetch_multiple_sources(
        self, sources: List[RSSSource], parallel: bool = False
    ) -> List[Article]:
        """
        从多个RSS源获取文章

        Args:
            sources: RSS源列表
            parallel: 是否并行获取（当前版本为串行）

        Returns:
            合并后的文章列表
        """
        all_articles = []

        logger.info(f"开始从 {len(sources)} 个RSS源获取文章")

        for source in sources:
            try:
                articles = self.fetch_source(source)
                all_articles.extend(articles)
                logger.debug(f"从 {source.name} 获取到 {len(articles)} 篇文章")
            except Exception as e:
                logger.error(f"处理RSS源失败 {source.name}: {e}")

        logger.info(f"总共获取到 {len(all_articles)} 篇文章")
        return all_articles

    def _parse_entry(self, entry: Dict[str, Any], source: RSSSource) -> Optional[Article]:
        """
        解析单个RSS条目

        Args:
            entry: RSS条目
            source: RSS源配置

        Returns:
            文章对象，如果解析失败则返回None
        """
        try:
            # 提取标题
            title = entry.get("title", "")
            if not title:
                logger.debug(f"文章缺少标题: {entry.get('link', '')}")
                return None

            # 提取链接
            link = entry.get("link", "")
            if not link:
                logger.debug(f"文章缺少链接: {title}")
                return None

            # 提取摘要
            summary = ""
            if "summary" in entry:
                summary = entry.get("summary", "")
            elif "description" in entry:
                summary = entry.get("description", "")

            # 提取发布时间
            published = ""
            if "published" in entry:
                published = entry.get("published", "")
            elif "updated" in entry:
                published = entry.get("updated", "")
            elif "pubDate" in entry:
                published = entry.get("pubDate", "")

            # 创建文章对象
            article = Article(
                title=title,
                link=link,
                source=source.name,
                summary=summary,
                published=published,
                category=source.category,
                language=source.language,
            )

            return article

        except Exception as e:
            logger.warning(f"解析RSS条目失败: {e}")
            return None

    def test_source(self, url: str) -> Dict[str, Any]:
        """
        测试RSS源是否可用

        Args:
            url: RSS源URL

        Returns:
            测试结果
        """
        try:
            feed_result = self.fetch_feed(url)
            entries = feed_result.get("entries", [])

            return {
                "success": True,
                "url": url,
                "title": feed_result.get("title", ""),
                "description": feed_result.get("description", ""),
                "article_count": len(entries),
                "sample_titles": [e.get("title", "") for e in entries[:3]],
                "status": feed_result.get("status", 0),
                "has_error": feed_result.get("bozo", False),
                "error_message": feed_result.get("bozo_exception", ""),
            }

        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
            }