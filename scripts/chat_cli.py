"""Unified local conversation entry. /birth JSON supplies explicit fields; /new starts a new task."""

import argparse
import asyncio
import json
import sys

from guanchen_v2.application.factory import open_application
from guanchen_v2.config.settings import Settings


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session")
    args = parser.parse_args()
    session_id = args.session
    async with open_application(Settings()) as app:
        print('输入 /birth {"year":1992,...} 补充资料，/new 问题切换任务，/quit 退出。')
        while True:
            query = input("> ").strip()
            if query == "/quit":
                return
            if not query:
                continue
            kwargs = {}
            if query.startswith("/birth "):
                kwargs["birth_patch"] = json.loads(query[7:])
                query = "补充出生资料"
            elif query.startswith("/new "):
                kwargs["new_task"] = True
                query = query[5:]
            result = await app.execute(session_id, query, **kwargs)
            session_id = result.session_id
            print(f"会话 {session_id} / {result.status}\n{result.content}")
            for citation in result.citations:
                print(f"来源：{citation.source_title} / {citation.section} / {citation.chunk_id}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
