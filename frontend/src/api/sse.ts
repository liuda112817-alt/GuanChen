import type { StreamEvent } from "./types";
// Frames may span reads, UTF-8 codepoints, and CRLF boundaries.
export async function readSSE(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: StreamEvent) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  const emit = (frame: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of frame.split(/\r\n|\r|\n/)) {
      if (line.startsWith(":")) continue;
      const split = line.indexOf(":");
      const key = split < 0 ? line : line.slice(0, split);
      let value = split < 0 ? "" : line.slice(split + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (key === "event") event = value;
      if (key === "data") data.push(value);
    }
    if (data.length) {
      onEvent({ event, data: JSON.parse(data.join("\n")) });
      if (event === "done" || event === "error") terminal = true;
    }
  };
  try {
    while (!terminal) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let match: RegExpExecArray | null;
      while ((match = /\r\n\r\n|\n\n|\r\r/.exec(buffer))) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        emit(frame);
        if (terminal) break;
      }
      if (done) {
        if (!terminal)
          throw new Error("连接中断了。已收到的内容还在，请先读取会话状态。");
        break;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
