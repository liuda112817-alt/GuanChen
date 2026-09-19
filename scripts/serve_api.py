"""Run the local Stage 11 backend, including psycopg-compatible Windows loop."""

import argparse
import asyncio
import sys

import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    config = uvicorn.Config("guanchen_v2.api.app:app", host="127.0.0.1", port=args.port, loop="none")
    asyncio.run(uvicorn.Server(config).serve())
