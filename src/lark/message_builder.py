"""
飞书消息构建模块
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..utils.logger import get_logger

logger = get_logger()


class MessageBuilder:
    """
    飞书消息构建器，支持多种消息格式
    """

    @staticmethod
    def build_text_message(text: str) -> Dict[str, Any]:
        """
        构建文本消息

        Args:
            text: 文本内容

        Returns:
            文本消息字典
        """
        return {"text": text}

    @staticmethod
    def build_article_card(
        title: str,
        link: str,
        summary: str = "",
        source: str = "",
        publish_time: str = "",
        category: str = "AI",
        language: str = "zh",
    ) -> Dict[str, Any]:
        """
        构建单篇文章卡片

        Args:
            title: 文章标题
            link: 文章链接
            summary: 文章摘要
            source: 文章来源
            publish_time: 发布时间
            category: 文章分类
            language: 语言

        Returns:
            消息卡片字典
        """
        # 格式化标题（截断避免过长）
        display_title = title[:100] + "..." if len(title) > 100 else title

        # 格式化摘要
        if summary:
            display_summary = summary[:200] + "..." if len(summary) > 200 else summary
        else:
            display_summary = "暂无摘要"

        # 格式化发布时间
        display_time = publish_time
        if publish_time:
            try:
                # 尝试解析常见时间格式
                for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        dt = datetime.strptime(publish_time, fmt)
                        display_time = dt.strftime("%Y-%m-%d %H:%M")
                        break
                    except ValueError:
                        continue
            except Exception:
                pass  # 保持原时间字符串

        # 构建卡片
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📰 {display_title}"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**摘要**: {display_summary}"
                    }
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**来源**: {source or '未知来源'}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**分类**: {category}"
                            }
                        }
                    ]
                }
            ]
        }

        # 添加发布时间（如果有）
        if display_time:
            card["elements"][1]["fields"].append({
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**时间**: {display_time}"
                }
            })

        # 添加操作按钮
        card["elements"].append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "阅读原文"},
                    "type": "primary",
                    "url": link
                }
            ]
        })

        return card

    @staticmethod
    def build_daily_digest_card(
        articles: List[Dict[str, Any]],
        date: str = None,
        title: str = "AI资讯日报",
    ) -> Dict[str, Any]:
        """
        构建每日摘要卡片

        Args:
            articles: 文章列表，每个文章是包含title, link, source等字段的字典
            date: 日期，默认为当天
            title: 卡片标题

        Returns:
            摘要卡片字典
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # 按来源分组
        articles_by_source = {}
        for article in articles:
            source = article.get("source", "其他")
            if source not in articles_by_source:
                articles_by_source[source] = []
            articles_by_source[source].append(article)

        # 构建卡片元素
        elements = []

        # 标题和日期
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"## {title}\n**日期**: {date}\n**文章总数**: {len(articles)}"
            }
        })

        # 各来源文章列表
        for source, source_articles in articles_by_source.items():
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"### 📋 {source} ({len(source_articles)}篇)"
                }
            })

            # 每篇文章
            for i, article in enumerate(source_articles[:5]):  # 每个来源最多显示5篇
                title = article.get("title", "无标题")
                link = article.get("link", "")
                # 截断标题
                display_title = title[:80] + "..." if len(title) > 80 else title

                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{i+1}. [{display_title}]({link})"
                    }
                })

            # 如果文章超过5篇，显示更多提示
            if len(source_articles) > 5:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"... 还有 {len(source_articles) - 5} 篇文章"
                    }
                })

            elements.append({"tag": "hr"})

        # 移除最后一个分割线
        if elements and elements[-1].get("tag") == "hr":
            elements.pop()

        # 添加查看全部按钮
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "📊 查看详细统计"},
                    "type": "default",
                    "url": ""  # 可以链接到统计页面
                }
            ]
        })

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 {title}"
                }
            },
            "elements": elements
        }

        return card

    @staticmethod
    def build_error_card(
        error_message: str,
        error_type: str = "系统错误",
        suggestion: str = "请检查配置或联系管理员",
        timestamp: str = None,
    ) -> Dict[str, Any]:
        """
        构建错误通知卡片

        Args:
            error_message: 错误信息
            error_type: 错误类型
            suggestion: 建议操作
            timestamp: 时间戳

        Returns:
            错误卡片字典
        """
        if not timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "⚠️ 系统错误通知"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**错误类型**: {error_type}\n**发生时间**: {timestamp}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**错误详情**:\n```\n{error_message[:500]}\n```"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**建议操作**: {suggestion}"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🔄 重新尝试"},
                            "type": "primary",
                            "value": {"action": "retry"}
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📋 查看日志"},
                            "type": "default",
                            "url": ""  # 可以链接到日志页面
                        }
                    ]
                }
            ]
        }

        return card

    @staticmethod
    def build_mixed_message(
        articles: List[Dict[str, Any]],
        max_text_articles: int = 3,
        include_digest: bool = True,
    ) -> Dict[str, Any]:
        """
        构建混合消息（文本摘要 + 详细卡片）

        Args:
            articles: 文章列表
            max_text_articles: 文本摘要中显示的最大文章数
            include_digest: 是否包含摘要卡片

        Returns:
            包含文本和卡片的消息字典
        """
        result = {
            "text_message": None,
            "card_messages": []
        }

        # 构建文本摘要
        if articles:
            text_lines = ["📰 AI资讯摘要"]
            text_lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d')}")
            text_lines.append("")

            for i, article in enumerate(articles[:max_text_articles]):
                title = article.get("title", "无标题")
                link = article.get("link", "")
                source = article.get("source", "未知来源")

                # 截断标题
                display_title = title[:60] + "..." if len(title) > 60 else title
                text_lines.append(f"{i+1}. {display_title}")
                text_lines.append(f"   来源: {source}")
                text_lines.append(f"   链接: {link}")
                text_lines.append("")

            if len(articles) > max_text_articles:
                text_lines.append(f"... 还有 {len(articles) - max_text_articles} 篇文章")

            result["text_message"] = "\n".join(text_lines)

        # 构建详细卡片（每篇文章一个卡片）
        if include_digest and articles:
            # 先添加每日摘要卡片
            digest_card = MessageBuilder.build_daily_digest_card(articles)
            result["card_messages"].append(digest_card)

            # 然后为每篇文章添加详细卡片（可选，可能太多）
            # for article in articles[:3]:  # 最多3篇详细卡片
            #     card = MessageBuilder.build_article_card(
            #         title=article.get("title"),
            #         link=article.get("link"),
            #         summary=article.get("summary"),
            #         source=article.get("source"),
            #         publish_time=article.get("publish_time"),
            #         category=article.get("category", "AI")
            #     )
            #     result["card_messages"].append(card)

        return result