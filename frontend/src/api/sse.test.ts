import { describe, it, expect } from "vitest";
import { readSSE } from "./sse";
const bytes = new TextEncoder();
function chunks(items: Uint8Array[]) {
  return new ReadableStream<Uint8Array>({
    start(c) {
      items.forEach((x) => c.enqueue(x));
      c.close();
    },
  });
}
describe("SSE transport", () => {
  it("handles UTF-8 split byte by byte, CRLF, comments and multiple frames", async () => {
    const raw =
      ': heartbeat\r\n\r\nevent: token\r\ndata: {"text":"观尘"}\r\n\r\nevent: done\r\ndata: {"content":"完整"}\r\n\r\n';
    const events: unknown[] = [];
    await readSSE(
      chunks([...bytes.encode(raw)].map((x) => new Uint8Array([x]))),
      (e) => events.push(e),
    );
    expect(events).toEqual([
      { event: "token", data: { text: "观尘" } },
      { event: "done", data: { content: "完整" } },
    ]);
  });
  it("handles multiline data", async () => {
    const events: unknown[] = [];
    await readSSE(
      chunks([bytes.encode('event: done\ndata: {\ndata: "content":"好"}\n\n')]),
      (e) => events.push(e),
    );
    expect(events).toEqual([{ event: "done", data: { content: "好" } }]);
  });
  it("rejects a truncated stream instead of silently reporting success", async () => {
    await expect(
      readSSE(
        chunks([bytes.encode('event: token\ndata: {"text":"部分"}\n\n')]),
        () => {},
      ),
    ).rejects.toThrow("连接中断");
  });
  it("ends on error without requiring done", async () => {
    const events: unknown[] = [];
    await readSSE(
      chunks([bytes.encode('event: error\ndata: {"code":"TIMEOUT"}\n\n')]),
      (e) => events.push(e),
    );
    expect(events).toHaveLength(1);
  });
});
