import { useEffect, useState } from "react";
import type { BirthProfile } from "../api/types";
export const profileLabels: Record<string, string> = {
  year: "出生年（公历）",
  month: "月",
  day: "日",
  hour: "小时（0–23）",
  minute: "分钟",
  gender: "排盘性别参数",
  birth_place_text: "出生地（选填）",
};
const ranges: Record<string, [number, number]> = {
  year: [1, 9999],
  month: [1, 12],
  day: [1, 31],
  hour: [0, 23],
  minute: [0, 59],
};
export function ProfileForm({
  initial = {},
  fields = Object.keys(profileLabels),
  busy = false,
  submit,
  label = "保存资料",
}: {
  initial?: BirthProfile;
  fields?: string[];
  busy?: boolean;
  submit: (profile: BirthProfile) => Promise<void>;
  label?: string;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setValues(
      Object.fromEntries(
        Object.entries(initial).map(([k, v]) => [
          k,
          v == null ? "" : String(v),
        ]),
      ),
    );
  }, [JSON.stringify(initial)]);
  return (
    <form
      className="profile-form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (saving || busy) return;
        setError("");
        const patch: Record<string, unknown> = {};
        for (const k of fields) {
          if (values[k]?.trim())
            patch[k] = ranges[k] ? Number(values[k]) : values[k].trim();
          else if (initial[k as keyof BirthProfile] != null) patch[k] = null;
        }
        const all = { ...initial, ...patch } as BirthProfile;
        if (all.year != null && all.month != null && all.day != null) {
          const date = new Date(0);
          date.setFullYear(all.year, all.month - 1, all.day);
          if (
            date.getFullYear() !== all.year ||
            date.getMonth() !== all.month - 1 ||
            date.getDate() !== all.day
          ) {
            setError("这个日期不存在，请检查年月日。");
            return;
          }
        }
        if (!Object.keys(patch).length) {
          setError("先填写一点资料，再保存。");
          return;
        }
        setSaving(true);
        try {
          await submit(patch as BirthProfile);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setSaving(false);
        }
      }}
    >
      <div className="field-grid">
        {fields
          .filter((k) => profileLabels[k])
          .map((k) => (
            <label key={k}>
              {profileLabels[k]}
              {k === "gender" ? (
                <select
                  value={values[k] ?? ""}
                  onChange={(e) =>
                    setValues({ ...values, [k]: e.target.value })
                  }
                >
                  <option value="">请选择</option>
                  <option value="male">男</option>
                  <option value="female">女</option>
                </select>
              ) : (
                <input
                  type={ranges[k] ? "number" : "text"}
                  min={ranges[k]?.[0]}
                  max={ranges[k]?.[1]}
                  step={ranges[k] ? 1 : undefined}
                  value={values[k] ?? ""}
                  onChange={(e) =>
                    setValues({ ...values, [k]: e.target.value })
                  }
                  placeholder="尚未填写"
                />
              )}
            </label>
          ))}
      </div>
      <p className="muted small">
        按当地民用时间填写。不确定的时间可以先留空，别替自己猜一个。
      </p>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <button className="primary" disabled={busy || saving}>
        {saving ? "保存中…" : label}
      </button>
    </form>
  );
}
