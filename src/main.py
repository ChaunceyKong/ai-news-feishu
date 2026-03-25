#!/usr/bin/env python3
"""
AI新闻推送飞书工具 - 主入口点
"""

import argparse
import sys
import logging
from typing import Optional

from .config import get_config
from .rss.fetcher import RSSFetcher
from .rss.models import RSSSource
from .lark.client import LarkClient
from .content_processor import ContentProcessor
from .utils.logger import get_logger
from .storage.database import get_storage

logger = get_logger()


def setup_argparse() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="AI新闻推送飞书工具 - 自动获取AI新闻并推送到飞书",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s run                # 运行一次新闻推送
  %(prog)s run --dry-run      # 干跑模式（不实际发送消息）
  %(prog)s test-config        # 测试配置和连接
  %(prog)s list-sources       # 列出所有RSS源
  %(prog)s clean-db --days 30 # 清理30天前的数据库记录
  %(prog)s stats              # 显示统计数据
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run命令
    run_parser = subparsers.add_parser("run", help="运行新闻推送")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式，不实际发送消息",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="最大处理文章数量（默认：50）",
    )
    run_parser.add_argument(
        "--message-type",
        choices=["text", "card", "mixed"],
        default="mixed",
        help="消息类型（默认：mixed）",
    )

    # test-config命令
    test_parser = subparsers.add_parser("test-config", help="测试配置和连接")

    # list-sources命令
    list_parser = subparsers.add_parser("list-sources", help="列出所有RSS源")

    # clean-db命令
    clean_parser = subparsers.add_parser("clean-db", help="清理数据库旧记录")
    clean_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="清理多少天前的记录（默认：30）",
    )

    # stats命令
    stats_parser = subparsers.add_parser("stats", help="显示统计数据")
    stats_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="统计最近多少天的数据（默认：7）",
    )

    # version命令
    subparsers.add_parser("version", help="显示版本信息")

    return parser


def run_news_push(
    dry_run: bool = False,
    limit: int = 50,
    message_type: str = "mixed",
) -> bool:
    """
    运行新闻推送

    Args:
        dry_run: 干跑模式
        limit: 最大处理文章数量
        message_type: 消息类型

    Returns:
        是否成功
    """
    logger.info("开始运行新闻推送...")
    logger.info(f"干跑模式: {dry_run}, 最大文章数: {limit}, 消息类型: {message_type}")

    try:
        # 加载配置
        config = get_config()
        if not config.validate():
            logger.error("配置验证失败，请检查配置文件")
            return False

        # 获取RSS源
        sources_data = config.get_rss_sources()
        sources = [RSSSource.from_dict(s) for s in sources_data]
        enabled_sources = [s for s in sources if s.enabled]

        if not enabled_sources:
            logger.error("没有启用的RSS源")
            return False

        logger.info(f"使用 {len(enabled_sources)} 个启用的RSS源")

        # 初始化组件
        fetcher = RSSFetcher(
            timeout=config.get_settings().get("fetch_timeout", 10),
            user_agent="AI-News-Feishu-Bot/1.0",
        )
        processor = ContentProcessor(config)

        # 获取文章
        logger.info("开始获取RSS文章...")
        articles = fetcher.fetch_multiple_sources(enabled_sources)
        logger.info(f"总共获取到 {len(articles)} 篇文章")

        if not articles:
            logger.info("没有获取到新文章")
            return True

        # 处理文章（去重、过滤、排序）
        logger.info("处理文章...")
        processed_articles = processor.process_articles(
            articles,
            filter_duplicates=config.get_settings().get("enable_duplicate_check", True),
        )

        if not processed_articles:
            logger.info("没有需要处理的新文章")
            return True

        # 限制文章数量
        if len(processed_articles) > limit:
            logger.info(f"限制文章数量: {len(processed_articles)} -> {limit}")
            processed_articles = processed_articles[:limit]

        # 构建消息
        logger.info(f"为 {len(processed_articles)} 篇文章构建消息...")
        messages = processor.build_messages(
            processed_articles,
            message_type=message_type,
            max_text_articles=3,
            include_digest=True,
        )

        # 发送消息
        if not dry_run:
            # 初始化飞书客户端
            lark_config = config.get_lark_config()
            lark_client = LarkClient(
                app_id=lark_config["app_id"],
                app_secret=lark_config["app_secret"],
                timeout=config.get_settings().get("fetch_timeout", 10),
            )

            # 发送文本消息（如果有）
            text_message = messages.get("text_message")
            if text_message:
                logger.info("发送文本消息...")
                try:
                    result = lark_client.send_text_message(
                        receiver_id=lark_config["receiver_id"],
                        text=text_message,
                        receiver_type=lark_config.get("receiver_type", "chat"),
                    )
                    logger.info(f"文本消息发送成功: {result.get('message_id')}")
                except Exception as e:
                    logger.error(f"发送文本消息失败: {e}")
                    # 继续发送卡片消息

            # 发送卡片消息（如果有）
            card_messages = messages.get("card_messages", [])
            for i, card in enumerate(card_messages):
                logger.info(f"发送卡片消息 {i+1}/{len(card_messages)}...")
                try:
                    result = lark_client.send_interactive_message(
                        receiver_id=lark_config["receiver_id"],
                        card_content=card,
                        receiver_type=lark_config.get("receiver_type", "chat"),
                    )
                    logger.info(f"卡片消息发送成功: {result.get('message_id')}")
                except Exception as e:
                    logger.error(f"发送卡片消息失败: {e}")

            # 标记文章为已处理
            if processed_articles:
                count = processor.mark_articles_processed(processed_articles)
                logger.info(f"标记了 {count} 篇文章为已处理")

            # 生成报告
            report = processor.generate_report(processed_articles)
            logger.info(f"处理报告: 总共 {report['total']} 篇文章")
            logger.info(f"按来源: {report['by_source']}")
            logger.info(f"按分类: {report['by_category']}")
            logger.info(f"关键词: {report.get('top_keywords', [])}")

        else:
            logger.info("干跑模式，跳过消息发送")
            logger.info(f"文本消息预览: {messages.get('text_message', '无')}")
            logger.info(f"卡片消息数量: {len(messages.get('card_messages', []))}")

            # 显示文章摘要
            logger.info("将处理的文章:")
            for i, article in enumerate(processed_articles[:5]):
                logger.info(f"{i+1}. {article.title} ({article.source})")

            if len(processed_articles) > 5:
                logger.info(f"... 还有 {len(processed_articles) - 5} 篇文章")

        logger.info("新闻推送完成")
        return True

    except Exception as e:
        logger.error(f"新闻推送失败: {e}", exc_info=True)
        return False


def test_configuration() -> bool:
    """测试配置和连接"""
    logger.info("测试配置和连接...")

    try:
        # 加载配置
        config = get_config()
        if not config.validate():
            logger.error("配置验证失败")
            return False

        logger.info("✓ 配置验证通过")

        # 测试RSS源
        sources_data = config.get_rss_sources()
        sources = [RSSSource.from_dict(s) for s in sources_data]
        enabled_sources = [s for s in sources if s.enabled]

        logger.info(f"找到 {len(enabled_sources)} 个启用的RSS源")

        # 测试每个RSS源
        fetcher = RSSFetcher(timeout=10)
        for source in enabled_sources[:3]:  # 测试前3个源
            logger.info(f"测试RSS源: {source.name} ({source.url})")
            try:
                result = fetcher.test_source(source.url)
                if result["success"]:
                    logger.info(f"  ✓ 可用: {result['article_count']} 篇文章")
                    logger.info(f"     标题: {result['title']}")
                else:
                    logger.warning(f"  ✗ 不可用: {result['error']}")
            except Exception as e:
                logger.warning(f"  ✗ 测试失败: {e}")

        # 测试飞书连接
        lark_config = config.get_lark_config()
        if lark_config["app_id"] and lark_config["app_secret"]:
            logger.info("测试飞书连接...")
            try:
                client = LarkClient(
                    app_id=lark_config["app_id"],
                    app_secret=lark_config["app_secret"],
                    timeout=10,
                )
                if client.test_connection():
                    logger.info("✓ 飞书连接成功")
                else:
                    logger.warning("✗ 飞书连接失败")
            except Exception as e:
                logger.warning(f"✗ 飞书连接测试异常: {e}")
        else:
            logger.warning("飞书配置不完整，跳过连接测试")

        # 测试数据库
        logger.info("测试数据库...")
        try:
            storage = get_storage()
            # 尝试简单的查询
            stats = storage.get_processed_stats(days=1)
            logger.info(f"✓ 数据库连接正常，最近1天处理了 {stats.get('total_count', 0)} 篇文章")
        except Exception as e:
            logger.warning(f"✗ 数据库连接异常: {e}")

        logger.info("配置测试完成")
        return True

    except Exception as e:
        logger.error(f"配置测试失败: {e}", exc_info=True)
        return False


def list_rss_sources() -> bool:
    """列出所有RSS源"""
    logger.info("列出所有RSS源...")

    try:
        config = get_config()
        sources_data = config.get_rss_sources()
        sources = [RSSSource.from_dict(s) for s in sources_data]

        if not sources:
            logger.info("没有配置RSS源")
            return True

        logger.info(f"总共 {len(sources)} 个RSS源:")
        for i, source in enumerate(sources):
            status = "✓ 启用" if source.enabled else "✗ 禁用"
            logger.info(f"{i+1}. {source.name}")
            logger.info(f"   地址: {source.url}")
            logger.info(f"   状态: {status}")
            logger.info(f"   分类: {source.category}, 语言: {source.language}")
            logger.info(f"   最大文章数: {source.max_articles}")
            if source.description:
                logger.info(f"   描述: {source.description}")
            logger.info("")

        return True

    except Exception as e:
        logger.error(f"列出RSS源失败: {e}")
        return False


def clean_database(days: int = 30) -> bool:
    """清理数据库旧记录"""
    logger.info(f"清理 {days} 天前的数据库记录...")

    try:
        storage = get_storage()
        deleted_count = storage.clean_old_records(days)

        logger.info(f"清理完成，删除了 {deleted_count} 条记录")
        return True

    except Exception as e:
        logger.error(f"清理数据库失败: {e}")
        return False


def show_statistics(days: int = 7) -> bool:
    """显示统计数据"""
    logger.info(f"显示最近 {days} 天的统计数据...")

    try:
        storage = get_storage()
        stats = storage.get_processed_stats(days)

        logger.info("=== 处理统计 ===")
        logger.info(f"统计周期: 最近 {days} 天")
        logger.info(f"总处理文章数: {stats.get('total_count', 0)}")

        # 按来源统计
        by_source = stats.get('by_source', {})
        if by_source:
            logger.info("\n按来源统计:")
            for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {source}: {count} 篇")

        # 按分类统计
        by_category = stats.get('by_category', {})
        if by_category:
            logger.info("\n按分类统计:")
            for category, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {category}: {count} 篇")

        # 每日统计
        daily_stats = stats.get('daily_stats', {})
        if daily_stats:
            logger.info("\n每日统计:")
            for date, count in sorted(daily_stats.items(), reverse=True):
                logger.info(f"  {date}: {count} 篇")

        return True

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return False


def show_version() -> bool:
    """显示版本信息"""
    version = "1.0.0"
    logger.info(f"AI新闻推送飞书工具 v{version}")
    logger.info("GitHub: https://github.com/yourusername/ai-news-feishu")
    logger.info("功能: 自动获取AI新闻并推送到飞书")
    return True


def main() -> int:
    """主函数"""
    parser = setup_argparse()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 设置日志级别
    if args.command == "run" and getattr(args, "dry_run", False):
        # 干跑模式使用更详细的日志
        logging.getLogger().setLevel(logging.INFO)
    else:
        # 其他命令使用默认级别
        pass

    # 执行命令
    success = False
    if args.command == "run":
        success = run_news_push(
            dry_run=args.dry_run,
            limit=args.limit,
            message_type=args.message_type,
        )
    elif args.command == "test-config":
        success = test_configuration()
    elif args.command == "list-sources":
        success = list_rss_sources()
    elif args.command == "clean-db":
        success = clean_database(days=args.days)
    elif args.command == "stats":
        success = show_statistics(days=args.days)
    elif args.command == "version":
        success = show_version()
    else:
        logger.error(f"未知命令: {args.command}")
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())