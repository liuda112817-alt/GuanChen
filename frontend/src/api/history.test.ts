import { it, expect } from "vitest";
import { restoreMessages } from "./history";
it("restores confirmations as product copy without leaking transport JSON", () => {
  const messages = restoreMessages({
    messages: [
      { role: "user", content: '{"action":"confirm"}' },
      {
        role: "user",
        content: '{"action":"modify","modification":"换个问题"}',
      },
      { role: "user", content: '{"action":"cancel"}' },
      {
        role: "user",
        content: '{"action":"something","text":"ordinary user JSON"}',
      },
    ],
    last_response: null,
    interrupt: null,
  });
  expect(messages.map((m) => m.content)).toEqual([
    "确认起卦",
    "修改问题：换个问题",
    "先不占",
    '{"action":"something","text":"ordinary user JSON"}',
  ]);
});
