"""
配置管理模块
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器，负责加载和管理所有配置"""

    def __init__(self, config_dir: str = None, env_file: str = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置目录路径，默认为项目根目录下的config目录
            env_file: 环境变量文件路径，默认为项目根目录下的.env文件
        """
        # 确定项目根目录
        self.project_root = Path(__file__).parent.parent.parent

        # 设置配置目录
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = self.project_root / "config"

        # 加载环境变量
        if env_file:
            env_path = Path(env_file)
        else:
            env_path = self.project_root / ".env"

        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"已加载环境变量文件: {env_path}")
        else:
            logger.warning(f"环境变量文件不存在: {env_path}")

        # 配置缓存
        self._config_cache: Dict[str, Any] = {}

        # 初始化配置
        self._load_all_configs()

    def _load_all_configs(self):
        """加载所有配置"""
        try:
            # 加载主配置
            main_config_path = self.config_dir / "config.yaml"
            if main_config_path.exists():
                self._config_cache["main"] = self._load_yaml(main_config_path)
                logger.info(f"已加载主配置文件: {main_config_path}")
            else:
                self._config_cache["main"] = {}
                logger.warning(f"主配置文件不存在: {main_config_path}")

            # 加载RSS源配置
            rss_config_path = self.config_dir / "rss_sources.yaml"
            if rss_config_path.exists():
                self._config_cache["rss_sources"] = self._load_yaml(rss_config_path)
                logger.info(f"已加载RSS源配置文件: {rss_config_path}")
            else:
                self._config_cache["rss_sources"] = {"sources": [], "categories": {}}
                logger.warning(f"RSS源配置文件不存在: {rss_config_path}")

        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            raise

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """加载YAML文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 替换环境变量占位符
                content = self._replace_env_vars(content)
                return yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML解析错误 {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            raise

    def _replace_env_vars(self, content: str) -> str:
        """替换内容中的环境变量占位符"""
        import re

        def replace_match(match):
            env_var = match.group(1)
            # 尝试从环境变量获取
            env_value = os.getenv(env_var)
            if env_value is not None:
                return env_value
            # 如果环境变量不存在，返回原占位符
            return match.group(0)

        # 匹配 ${VAR_NAME} 格式
        pattern = r'\$\{([A-Za-z0-9_]+)\}'
        return re.sub(pattern, replace_match, content)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点分隔符访问嵌套字典

        Args:
            key: 配置键，如 "lark.app_id" 或 "settings.fetch_timeout"
            default: 默认值，如果键不存在则返回此值

        Returns:
            配置值
        """
        try:
            # 分割键为部分
            parts = key.split('.')

            # 确定从哪个配置部分开始查找
            if parts[0] in self._config_cache:
                current = self._config_cache[parts[0]]
                parts = parts[1:]
            else:
                current = self._config_cache.get("main", {})

            # 遍历嵌套字典
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default

            return current
        except (KeyError, AttributeError, IndexError):
            return default

    def get_lark_config(self) -> Dict[str, Any]:
        """获取飞书配置"""
        return {
            "app_id": self.get("lark.app_id") or os.getenv("LARK_APP_ID"),
            "app_secret": self.get("lark.app_secret") or os.getenv("LARK_APP_SECRET"),
            "receiver_id": self.get("lark.receiver_id") or os.getenv("LARK_RECEIVER_ID"),
            "receiver_type": self.get("lark.receiver_type", "chat"),
        }

    def get_rss_sources(self) -> List[Dict[str, Any]]:
        """获取启用的RSS源列表"""
        # 首先尝试从rss_sources配置获取
        sources = self._config_cache.get("rss_sources", {}).get("sources", [])

        if not sources:
            # 回退到主配置中的rss_sources
            sources = self.get("rss_sources", [])

        # 过滤启用的源
        enabled_sources = [s for s in sources if s.get("enabled", True)]

        # 确保每个源都有必要的字段
        for source in enabled_sources:
            source.setdefault("max_articles", 10)
            source.setdefault("category", "AI")
            source.setdefault("language", "en")

        return enabled_sources

    def get_settings(self) -> Dict[str, Any]:
        """获取运行设置"""
        settings = self.get("settings", {})

        # 使用环境变量覆盖配置
        env_settings = {
            "fetch_timeout": int(os.getenv("FETCH_TIMEOUT", settings.get("fetch_timeout", 10))),
            "fetch_retry_times": int(os.getenv("FETCH_RETRY_TIMES", settings.get("fetch_retry_times", 3))),
            "send_batch_size": int(os.getenv("SEND_BATCH_SIZE", settings.get("send_batch_size", 5))),
            "clean_old_days": int(os.getenv("CLEAN_OLD_DAYS", settings.get("clean_old_days", 30))),
            "log_level": os.getenv("LOG_LEVEL", settings.get("log_level", "INFO")),
            "log_format": os.getenv("LOG_FORMAT", settings.get("log_format", "json")),
            "enable_duplicate_check": bool(os.getenv("ENABLE_DUPLICATE_CHECK",
                                                     str(settings.get("enable_duplicate_check", True)).lower()) == "true"),
            "enable_dry_run": bool(os.getenv("DRY_RUN",
                                            str(settings.get("enable_dry_run", False)).lower()) == "true"),
        }

        return env_settings

    def get_database_path(self) -> str:
        """获取数据库路径"""
        db_path = os.getenv("DATABASE_PATH")
        if db_path:
            return db_path

        # 默认路径：项目根目录下的data目录
        data_dir = self.project_root / "data"
        data_dir.mkdir(exist_ok=True)
        return str(data_dir / "news.db")

    def validate(self) -> bool:
        """验证配置是否完整"""
        errors = []

        # 检查飞书配置
        lark_config = self.get_lark_config()
        if not lark_config["app_id"]:
            errors.append("飞书app_id未配置")
        if not lark_config["app_secret"]:
            errors.append("飞书app_secret未配置")
        if not lark_config["receiver_id"]:
            errors.append("飞书接收者ID未配置")

        # 检查RSS源
        rss_sources = self.get_rss_sources()
        if not rss_sources:
            errors.append("未配置任何RSS源")

        if errors:
            logger.error("配置验证失败: " + "; ".join(errors))
            return False

        logger.info("配置验证通过")
        return True

    def reload(self):
        """重新加载所有配置"""
        self._config_cache.clear()
        self._load_all_configs()
        logger.info("配置已重新加载")


# 全局配置实例
_config_instance: Optional[ConfigManager] = None


def get_config(config_dir: str = None, env_file: str = None) -> ConfigManager:
    """获取全局配置实例（单例模式）"""
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigManager(config_dir, env_file)

    return _config_instance