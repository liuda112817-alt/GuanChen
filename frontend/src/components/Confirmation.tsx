import { useState } from "react";
import { Check, PenLine, X } from "lucide-react";
import type { Interrupt } from "../api/types";
export function Confirmation({
  value,
  busy,
  submit,
}: {
  value: Interrupt;
  busy: boolean;
  submit: (
    action: "confirm" | "modify" | "cancel",
    text?: string,
  ) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  return (
    <section className="confirmation">
      <span className="eyebrow">先把问题对一遍</span>
      <h3>先别急着落子。</h3>
      <p>{value.prompt}</p>
      {editing && (
        <label>
          你想怎么改？
          <textarea
            value={text}
            maxLength={12000}
            onChange={(e) => setText(e.target.value)}
            autoFocus
          />
        </label>
      )}
      <div className="button-row">
        <button
          className="primary"
          disabled={busy || (editing && !text.trim())}
          onClick={() =>
            void submit(
              editing ? "modify" : "confirm",
              editing ? text.trim() : undefined,
            )
          }
        >
          <Check size={16} />
          {editing ? "提交修改" : "确认起卦"}
        </button>
        <button
          className="quiet"
          disabled={busy}
          onClick={() => setEditing(!editing)}
        >
          <PenLine size={15} />
          {editing ? "返回确认" : "修改问题"}
        </button>
        <button
          className="quiet"
          disabled={busy}
          onClick={() => void submit("cancel")}
        >
          <X size={15} />
          先不占
        </button>
      </div>
      <p className="muted small">
        确认后才会进行一次确定性起卦。结果是一个观察角度，选择仍在你手里。
      </p>
    </section>
  );
}
