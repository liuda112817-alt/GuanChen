"""Official external MCP v2 client: HTTP auth, discovery and all three tools."""

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[2]


async def run_smoke():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    env = {**os.environ, "GUANCHEN_MCP_TOKEN": token, "PYTHONIOENCODING": "utf-8"}
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    with (report_dir / "mcp_server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "guanchen_v2.mcp.server", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            async with httpx2.AsyncClient(timeout=180, trust_env=False) as raw:
                deadline = time.monotonic() + 180
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("MCP server exited; inspect reports/mcp_server.log")
                    try:
                        response = await raw.post(url, json={})
                        assert response.status_code == 401, response.status_code
                        break
                    except httpx2.ConnectError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("MCP startup timed out")
                        await asyncio.sleep(0.5)
            async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=180, trust_env=False) as http:
                async with streamable_http_client(url, http_client=http) as (read, write):
                    async with ClientSession(read, write, read_timeout_seconds=180) as session:
                        await session.initialize()
                        names = {t.name for t in (await session.list_tools()).tools}
                        assert names == {"calculate_bazi", "knowledge_search", "cast_hexagram"}
                        inputs = {
                            "calculate_bazi": {"year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"},
                            "knowledge_search": {"query": "正官是什么意思"},
                            "cast_hexagram": {"method": "manual", "manual": {"lines": [7, 8, 7, 8, 7, 8]}},
                        }
                        calls = {}
                        for name, request in inputs.items():
                            result = await session.call_tool(name, {"request": request})
                            assert not result.is_error, (name, result.content)
                            data = json.loads(result.content[0].text)
                            if name == "knowledge_search":
                                assert data["results"] and all(r["citation"]["chunk_id"] for r in data["results"])
                            calls[name] = {"passed": True, "output": data}
                        bad = await session.call_tool("cast_hexagram", {"request": {"method": "invalid"}})
                        assert bad.is_error
                        report = {
                            "passed": True,
                            "transport": "streamable-http",
                            "unauthorized_rejected": True,
                            "invalid_input_rejected": True,
                            "tools": calls,
                        }
                        (report_dir / "mcp_smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                        print("MCP HTTP smoke: discovery, 3 real tools, auth and invalid input PASS", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    asyncio.run(run_smoke())
