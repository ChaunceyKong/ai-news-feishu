"""基础测试用例"""

import pytest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_import_modules():
    """测试模块导入"""
    # 测试核心模块导入
    from config import config_manager
    from rss import models, fetcher, parser
    from lark import client, message_builder
    from storage import database
    from utils import logger, retry_manager
    from content_processor import ContentProcessor

    assert config_manager is not None
    assert models is not None
    assert fetcher is not None
    assert parser is not None
    assert client is not None
    assert message_builder is not None
    assert database is not None
    assert logger is not None
    assert retry_manager is not None
    assert ContentProcessor is not None


def test_rss_models():
    """测试RSS数据模型"""
    from rss.models import Article, RSSSource

    # 测试Article模型
    article = Article(
        title="Test Article",
        link="https://example.com/test",
        source="Test Source",
        summary="Test summary",
        published="2024-01-01",
        category="AI",
        language="en"
    )

    assert article.title == "Test Article"
    assert article.link == "https://example.com/test"
    assert article.source == "Test Source"
    assert article.hash is not None
    assert article.is_valid() is True

    # 测试无效文章
    invalid_article = Article(
        title="",
        link="invalid-url",
        source="Test"
    )
    assert invalid_article.is_valid() is False

    # 测试RSSSource模型
    source = RSSSource(
        name="Test Source",
        url="https://example.com/rss",
        enabled=True,
        category="AI",
        language="en",
        max_articles=10
    )

    assert source.name == "Test Source"
    assert source.url == "https://example.com/rss"
    assert source.enabled is True
    assert source.is_valid() is True


def test_message_builder():
    """测试消息构建器"""
    from lark.message_builder import MessageBuilder

    # 测试文本消息
    text_message = MessageBuilder.build_text_message("Test message")
    assert text_message["text"] == "Test message"

    # 测试文章卡片
    card = MessageBuilder.build_article_card(
        title="Test Article",
        link="https://example.com",
        summary="Test summary",
        source="Test Source",
        publish_time="2024-01-01",
        category="AI",
        language="en"
    )

    assert "config" in card
    assert "header" in card
    assert "elements" in card
    assert card["config"]["wide_screen_mode"] is True

    # 测试每日摘要卡片
    articles = [
        {
            "title": "Article 1",
            "link": "https://example.com/1",
            "source": "Source 1",
            "summary": "Summary 1"
        },
        {
            "title": "Article 2",
            "link": "https://example.com/2",
            "source": "Source 2",
            "summary": "Summary 2"
        }
    ]

    digest_card = MessageBuilder.build_daily_digest_card(articles)
    assert "config" in digest_card
    assert "header" in digest_card
    assert "elements" in digest_card


def test_config_manager():
    """测试配置管理器"""
    from config.config_manager import ConfigManager

    # 使用测试配置目录
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试配置文件
        config_dir = os.path.join(tmpdir, "config")
        os.makedirs(config_dir)

        # 创建简单配置
        config_content = """
lark:
  app_id: "test_app_id"
  app_secret: "test_app_secret"
  receiver_id: "test_receiver"

rss_sources:
  - name: "Test Source"
    url: "https://example.com/rss"
    enabled: true
    max_articles: 5

settings:
  fetch_timeout: 5
  log_level: "INFO"
"""

        config_file = os.path.join(config_dir, "config.yaml")
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_content)

        # 创建RSS源配置
        rss_content = """
sources:
  - name: "Test Source 1"
    url: "https://example.com/rss1"
    enabled: true
  - name: "Test Source 2"
    url: "https://example.com/rss2"
    enabled: false
"""

        rss_file = os.path.join(config_dir, "rss_sources.yaml")
        with open(rss_file, "w", encoding="utf-8") as f:
            f.write(rss_content)

        # 测试配置加载
        config = ConfigManager(config_dir=config_dir)

        # 测试配置获取
        assert config.get("lark.app_id") == "test_app_id"
        assert config.get("settings.fetch_timeout") == 5

        # 测试RSS源获取
        sources = config.get_rss_sources()
        assert len(sources) == 1  # 只有启用的源
        assert sources[0]["name"] == "Test Source 1"

        # 测试设置获取
        settings = config.get_settings()
        assert settings["fetch_timeout"] == 5
        assert settings["log_level"] == "INFO"


def test_logger():
    """测试日志工具"""
    from utils.logger import setup_logger

    logger = setup_logger(name="test_logger", level="DEBUG", format_type="text")
    assert logger is not None
    assert logger.name == "test_logger"
    assert logger.level == 10  # DEBUG level


if __name__ == "__main__":
    pytest.main([__file__, "-v"])