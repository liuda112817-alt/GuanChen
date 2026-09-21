import type { Message, Session } from "./types";
function readableUserMessage(content: string) {
  // Resume commands are persisted as transport JSON by the domain service.
  try {
    const v = JSON.parse(content);
    if (
      v &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      Object.keys(v).every((k) => k === "action" || k === "modification")
    ) {
      if (v.action === "confirm") return "确认起卦";
      if (v.action === "cancel") return "先不占";
      if (v.action === "modify" && typeof v.modification === "string")
        return `修改问题：${v.modification}`;
    }
  } catch {
    /* Ordinary user prose. */
  }
  return content;
}
export function restoreMessages(s: Session): Message[] {
  const messages: Message[] = s.messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m, i) => ({
      id: `restored-${i}`,
      role: m.role as "user" | "assistant",
      content: m.role === "user" ? readableUserMessage(m.content) : m.content,
    }));
  if (s.last_response) {
    const last = messages.at(-1);
    if (last?.role === "assistant" && last.content === s.last_response.content)
      last.reply = s.last_response;
    else
      messages.push({
        id: "last-response",
        role: "assistant",
        content: s.last_response.content,
        reply: s.last_response,
      });
  }
  return messages;
}
