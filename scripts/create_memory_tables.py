import asyncio

from guanchen_v2.memory.database import engine
from guanchen_v2.memory.models import MemoryBase


async def main() -> None:
    """创建 Stage 8 全部 Memory 表（会话状态 + 长期用户资料域表）。"""
    async with engine.begin() as conn:
        await conn.run_sync(MemoryBase.metadata.create_all)
    print("Memory tables created.")


if __name__ == "__main__":
    asyncio.run(main())
