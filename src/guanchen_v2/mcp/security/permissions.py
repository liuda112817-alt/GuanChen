from enum import Enum


class Permission(str, Enum):
    """MCP 工具调用的权限定义"""
    BAZI_READ = "bazi.read"
    KNOWLEDGE_READ = "knowledge.read"
    LIUYAO_READ = "liuyao.read"