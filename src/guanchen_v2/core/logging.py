import logging


def configure_logging(level: str) -> None:
    """配置全局基础日志系统。仅在应用入口点（如 CLI、脚本启动或 FastAPI 启动时）调用。"""
    numeric_level = getattr(logging, level)

    logging.basicConfig(level=numeric_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
