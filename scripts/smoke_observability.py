import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).parent.parent

async def run_smoke():
    print("=" * 60)
    print("GuanChen Observability E2E Smoke Test")
    print("=" * 60)
    
    print("\n[Test] Starting MCP Server via stdio to verify Trace injection...")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "guanchen_v2.mcp.server"],
        env={"PYTHONPATH": str(PROJECT_ROOT / "src")}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("\n[Action] Calling 'bazi.calculate' over stdio stream...")
            result = await session.call_tool("bazi.calculate", arguments={
                "year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"
            })
            
            assert not result.isError, "Expected Tool to succeed!"
            print("\n✓ Tool invocation over stdio successful!")
            print("✓ stdout remains clean (no JSON-RPC corruption).")
            print("\nCheck your console (stderr) output above for the JSON trace logs!")
            print("=" * 60)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_smoke())
