"""Live progress; answer chunks are emitted only after complete output validation."""

import asyncio
import json
from contextlib import suppress

from guanchen_v2.api.errors import APIApplicationError
from guanchen_v2.application.progress import progress_sink

EVENT_TYPES = ("start", "route", "need_input", "tool_start", "tool_end", "retrieval", "token", "interrupt", "done", "error")


async def stream_events(operation, session_id: str, session_token: str | None = None):
    queue = asyncio.Queue()
    sequence = 0

    def encode(event, data):
        nonlocal sequence
        sequence += 1
        return f"id: {sequence}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def progress(event, data):
        queue.put_nowait((event, data))

    async def execute():
        token = progress_sink.set(progress)
        try:
            result = await operation()
            if result.status == "needs_input":
                progress("need_input", result.required_input.model_dump(mode="json"))
            if result.status == "interrupted":
                progress("interrupt", result.interrupt.model_dump(mode="json"))
            for offset in range(0, len(result.content), 120):
                progress("token", {"text": result.content[offset : offset + 120]})
            result.session_token = session_token
            progress("done", result.model_dump(mode="json"))
        except APIApplicationError as exc:
            progress("error", {"code": exc.code, "message": exc.message, "trace_id": exc.trace_id})
        except Exception:
            progress("error", {"code": "RUNTIME_ERROR", "message": "请求处理失败。", "trace_id": None})
        finally:
            progress_sink.reset(token)
            queue.put_nowait(None)

    # Start only once the consumer enters the protected generator lifetime.
    task = None
    try:
        yield encode("start", {"session_id": session_id, "session_token": session_token})
        task = asyncio.create_task(execute())
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if item is None:
                break
            yield encode(*item)
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
