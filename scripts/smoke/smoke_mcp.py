import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).parent.parent


async def run_smoke():
    print("=" * 60)
    print("GuanChen MCP Server E2E Smoke Test")
    print("=" * 60)

    # Test 1: Server 启动
    print("\n[Test 1] Starting MCP Server via stdio...")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "guanchen_v2.mcp.server"],
        env={"PYTHONPATH": str(PROJECT_ROOT / "src")}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ MCP Server started and session initialized.")

            # Test 2: Tool Discovery
            print("\n[Test 2] Requesting Tool Discovery (tools/list)...")
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"✓ Discovered tools: {tool_names}")
            
            assert "bazi.calculate" in tool_names, "Missing bazi.calculate"
            assert "knowledge.search" in tool_names, "Missing knowledge.search"
            assert "liuyao.cast_hexagram" in tool_names, "Missing liuyao.cast_hexagram"

            # Test 3: Tool Invocation (Valid)
            print("\n[Test 3] Invoking Tool (bazi.calculate) with valid input...")
            bazi_result = await session.call_tool("bazi.calculate", arguments={
                "year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"
            })
            
            assert not bazi_result.isError, "Expected success but got error."
            print(f"✓ Tool invocation successful. Response preview:")
            print(f"  {bazi_result.content[0].text[:150]}...")

            # Test 4: Error Handling (Invalid Input)
            print("\n[Test 4] Testing Error Handling with invalid input...")
            error_result = await session.call_tool("bazi.calculate", arguments={
                "year": "abc", "month": 1  # 故意给出错误类型且缺失字段
            })
            
            assert error_result.isError, "Expected isError=True for invalid input."
            print(f"✓ Error successfully caught and formatted by protocol:")
            print(f"  {error_result.content[0].text}")

    print("\n" + "=" * 60)
    print("✅ All MCP Smoke Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_smoke())