"""Verify real stdio compatibility and shared metadata-only trace lineage."""

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def run_smoke():
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "guanchen_v2.mcp.server", "--transport", "stdio"], cwd=str(ROOT))
    with TemporaryDirectory() as directory:
        path = Path(directory) / "stderr.log"
        with path.open("w", encoding="utf-8") as log:
            async with stdio_client(parameters, errlog=log) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=180) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "calculate_bazi", {"request": {"year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"}}
                    )
                    assert not result.is_error
        events = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
                if "trace_id" in event:
                    events.append(event)
            except ValueError:
                pass
        calls = [e for e in events if e["event_type"] == "TOOL_CALL"]
        assert len(calls) == 1
        steps = [e for e in events if e["trace_id"] == calls[0]["trace_id"]]
        assert {e["event_type"] for e in steps} >= {"REQUEST", "DISPATCH", "TOOL_CALL", "SERVICE_CALL", "TOOL"}
        assert all(e["status"] == "SUCCESS" for e in steps)
        print("stdio protocol and shared trace lineage PASS")


if __name__ == "__main__":
    # Client process needs the Windows subprocess-capable default Proactor loop.
    asyncio.run(run_smoke())
