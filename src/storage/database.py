"""
数据存储模块 - SQLite数据库管理
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from datetime import datetime, timedelta
from ..utils.logger import get_logger
from ..rss.models import Article

logger = get_logger()


class NewsStorage:
    """
    新闻数据存储管理器，使用SQLite数据库
    """

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，如果为None则使用默认路径
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            # 默认路径：项目根目录下的data目录
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            self.db_path = data_dir / "news.db"

        # 线程本地存储
        self._local = threading.local()

        # 初始化数据库
        self._init_database()

        logger.info(f"数据库初始化完成: {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """
        获取数据库连接（线程安全）

        Yields:
            SQLite连接对象
        """
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row

        try:
            yield self._local.conn
        except Exception as e:
            self._local.conn.rollback()
            raise e

    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            # 已处理文章表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL,
                    published_date TEXT,
                    source TEXT,
                    category TEXT DEFAULT 'AI',
                    language TEXT DEFAULT 'en',
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON processed_articles(article_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_articles(processed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON processed_articles(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON processed_articles(category)")

            # RSS源状态表（可选）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rss_source_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    last_fetched_at TIMESTAMP,
                    last_article_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def is_article_processed(self, article_hash: str) -> bool:
        """
        检查文章是否已处理

        Args:
            article_hash: 文章哈希值

        Returns:
            是否已处理
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_articles WHERE article_hash = ?",
                (article_hash,)
            )
            return cursor.fetchone() is not None

    def mark_article_processed(self, article: Article) -> bool:
        """
        标记文章为已处理

        Args:
            article: 文章对象

        Returns:
            是否成功标记
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO processed_articles
                    (article_hash, title, link, published_date, source, category, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.hash,
                    article.title,
                    article.link,
                    article.published,
                    article.source,
                    article.category,
                    article.language,
                ))
                conn.commit()

                # 更新文章的processed_at时间
                article.processed_at = datetime.now()

                logger.debug(f"标记文章为已处理: {article.title}")
                return True

        except sqlite3.Error as e:
            logger.error(f"标记文章失败: {e}")
            return False

    def filter_new_articles(self, articles: List[Article]) -> List[Article]:
        """
        过滤出未处理的新文章

        Args:
            articles: 文章列表

        Returns:
            未处理的新文章列表
        """
        if not articles:
            return []

        # 获取所有文章的哈希值
        hashes = [article.hash for article in articles]

        # 构建查询
        placeholders = ",".join(["?"] * len(hashes))

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"SELECT article_hash FROM processed_articles WHERE article_hash IN ({placeholders})",
                    hashes
                )
                existing_hashes = {row["article_hash"] for row in cursor}

            # 过滤出新文章
            new_articles = [a for a in articles if a.hash not in existing_hashes]

            logger.info(f"文章去重过滤: {len(articles)} -> {len(new_articles)}")
            return new_articles

        except sqlite3.Error as e:
            logger.error(f"过滤文章失败: {e}")
            # 出错时返回所有文章（避免因数据库问题导致无法推送）
            return articles

    def batch_mark_processed(self, articles: List[Article]) -> int:
        """
        批量标记文章为已处理

        Args:
            articles: 文章列表

        Returns:
            成功标记的数量
        """
        if not articles:
            return 0

        try:
            with self._get_connection() as conn:
                # 准备数据
                data = []
                current_time = datetime.now()

                for article in articles:
                    data.append((
                        article.hash,
                        article.title,
                        article.link,
                        article.published,
                        article.source,
                        article.category,
                        article.language,
                        current_time,
                    ))

                # 批量插入
                conn.executemany("""
                    INSERT OR IGNORE INTO processed_articles
                    (article_hash, title, link, published_date, source, category, language, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, data)

                conn.commit()

                count = conn.total_changes
                logger.info(f"批量标记 {count} 篇文章为已处理")

                # 更新文章的processed_at时间
                for article in articles:
                    article.processed_at = current_time

                return count

        except sqlite3.Error as e:
            logger.error(f"批量标记文章失败: {e}")
            return 0

    def clean_old_records(self, days: int = 30) -> int:
        """
        清理指定天数前的记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM processed_articles WHERE processed_at < ?",
                    (cutoff_str,)
                )
                conn.commit()

                deleted_count = cursor.rowcount
                logger.info(f"清理 {deleted_count} 条 {days} 天前的记录")

                # 执行VACUUM以回收空间（可选）
                if deleted_count > 1000:
                    conn.execute("VACUUM")
                    conn.commit()

                return deleted_count

        except sqlite3.Error as e:
            logger.error(f"清理旧记录失败: {e}")
            return 0

    def get_processed_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        获取处理统计信息

        Args:
            days: 统计最近多少天

        Returns:
            统计信息字典
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

            with self._get_connection() as conn:
                # 总文章数
                cursor = conn.execute(
                    "SELECT COUNT(*) as total FROM processed_articles WHERE processed_at >= ?",
                    (cutoff_str,)
                )
                total_count = cursor.fetchone()["total"]

                # 按来源统计
                cursor = conn.execute("""
                    SELECT source, COUNT(*) as count
                    FROM processed_articles
                    WHERE processed_at >= ?
                    GROUP BY source
                    ORDER BY count DESC
                """, (cutoff_str,))
                by_source = {row["source"]: row["count"] for row in cursor}

                # 按分类统计
                cursor = conn.execute("""
                    SELECT category, COUNT(*) as count
                    FROM processed_articles
                    WHERE processed_at >= ?
                    GROUP BY category
                    ORDER BY count DESC
                """, (cutoff_str,))
                by_category = {row["category"]: row["count"] for row in cursor}

                # 每日统计
                cursor = conn.execute("""
                    SELECT DATE(processed_at) as date, COUNT(*) as count
                    FROM processed_articles
                    WHERE processed_at >= ?
                    GROUP BY DATE(processed_at)
                    ORDER BY date DESC
                """, (cutoff_str,))
                daily_stats = {row["date"]: row["count"] for row in cursor}

                return {
                    "total_count": total_count,
                    "by_source": by_source,
                    "by_category": by_category,
                    "daily_stats": daily_stats,
                    "period_days": days,
                }

        except sqlite3.Error as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_count": 0,
                "by_source": {},
                "by_category": {},
                "daily_stats": {},
                "period_days": days,
                "error": str(e),
            }

    def update_rss_source_status(
        self,
        source_name: str,
        article_count: int = 0,
        error_message: str = None,
    ) -> bool:
        """
        更新RSS源状态

        Args:
            source_name: 源名称
            article_count: 获取到的文章数量
            error_message: 错误信息（如果有）

        Returns:
            是否成功更新
        """
        try:
            with self._get_connection() as conn:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if error_message:
                    conn.execute("""
                        INSERT OR REPLACE INTO rss_source_status
                        (source_name, last_fetched_at, last_article_count, last_error, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (source_name, current_time, article_count, error_message, current_time))
                else:
                    conn.execute("""
                        INSERT OR REPLACE INTO rss_source_status
                        (source_name, last_fetched_at, last_article_count, last_error, updated_at)
                        VALUES (?, ?, ?, NULL, ?)
                    """, (source_name, current_time, article_count, current_time))

                conn.commit()
                return True

        except sqlite3.Error as e:
            logger.error(f"更新RSS源状态失败: {e}")
            return False

    def get_rss_source_status(self, source_name: str = None) -> List[Dict[str, Any]]:
        """
        获取RSS源状态

        Args:
            source_name: 源名称，如果为None则获取所有源

        Returns:
            状态信息列表
        """
        try:
            with self._get_connection() as conn:
                if source_name:
                    cursor = conn.execute(
                        "SELECT * FROM rss_source_status WHERE source_name = ? ORDER BY updated_at DESC",
                        (source_name,)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT * FROM rss_source_status ORDER BY updated_at DESC"
                    )

                rows = cursor.fetchall()

                result = []
                for row in rows:
                    result.append({
                        "source_name": row["source_name"],
                        "last_fetched_at": row["last_fetched_at"],
                        "last_article_count": row["last_article_count"],
                        "last_error": row["last_error"],
                        "updated_at": row["updated_at"],
                    })

                return result

        except sqlite3.Error as e:
            logger.error(f"获取RSS源状态失败: {e}")
            return []

    def get_recently_processed_articles(
        self,
        limit: int = 20,
        source: str = None,
        category: str = None,
    ) -> List[Dict[str, Any]]:
        """
        获取最近处理的文章

        Args:
            limit: 返回数量
            source: 按来源筛选
            category: 按分类筛选

        Returns:
            文章信息列表
        """
        try:
            query = "SELECT * FROM processed_articles WHERE 1=1"
            params = []

            if source:
                query += " AND source = ?"
                params.append(source)

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY processed_at DESC LIMIT ?"
            params.append(limit)

            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                result = []
                for row in rows:
                    result.append({
                        "title": row["title"],
                        "link": row["link"],
                        "source": row["source"],
                        "category": row["category"],
                        "published_date": row["published_date"],
                        "processed_at": row["processed_at"],
                        "hash": row["article_hash"],
                    })

                return result

        except sqlite3.Error as e:
            logger.error(f"获取最近文章失败: {e}")
            return []

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, "conn"):
            try:
                self._local.conn.close()
                delattr(self._local, "conn")
            except Exception as e:
                logger.error(f"关闭数据库连接失败: {e}")


# 全局存储实例
_storage_instance: Optional[NewsStorage] = None


def get_storage(db_path: str = None) -> NewsStorage:
    """获取全局存储实例（单例模式）"""
    global _storage_instance

    if _storage_instance is None:
        _storage_instance = NewsStorage(db_path)

    return _storage_instance