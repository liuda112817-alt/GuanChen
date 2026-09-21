import { useEffect, useRef, useState } from "react";
import { api, ApiError, stream } from "../api/client";
import { restoreMessages } from "../api/history";
import {
  activeId,
  loadSessions,
  saveSessions,
  setActiveId,
} from "../api/storage";
import type {
  BirthProfile,
  Credential,
  Interrupt,
  Message,
  Reply,
  Session,
} from "../api/types";
const labels: Record<string, string> = {
  knowledge: "知识",
  bazi: "八字",
  dream: "梦境",
  liuyao: "六爻",
};
export function useConversation() {
  const [sessions, setSessions] = useState(loadSessions);
  const [current, setCurrent] = useState<Credential | null>(
    () => loadSessions().find((s) => s.session_id === activeId()) ?? null,
  );
  const currentRef = useRef(current);
  const list = useRef(sessions);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [reply, setReply] = useState<Reply | null>(null);
  const [interrupt, setInterrupt] = useState<Interrupt | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [needsRecovery, setNeedsRecovery] = useState(false);
  function remember(c: Credential) {
    const next = [
      c,
      ...list.current.filter((s) => s.session_id !== c.session_id),
    ];
    saveSessions(next);
    setActiveId(c.session_id);
    list.current = next;
    setSessions(next);
    currentRef.current = c;
    setCurrent(c);
  }
  async function ensure() {
    if (currentRef.current) return currentRef.current;
    const created = await api<{ session_id: string; session_token: string }>(
      "/sessions",
      null,
      "POST",
    );
    const c = { ...created, title: "新的问题", updated: Date.now() };
    remember(c);
    return c;
  }
  function showSession(s: Session) {
    setMessages(restoreMessages(s));
    setReply(s.last_response);
    setInterrupt(s.interrupt);
    setNeedsRecovery(false);
  }
  async function restore(c = currentRef.current) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      c = c ?? (await ensure());
      const s = await api<Session>(
        `/sessions/${encodeURIComponent(c.session_id)}`,
        c,
      );
      remember(c);
      showSession(s);
    } catch (e) {
      setError((e as Error).message);
      setNeedsRecovery(true);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    if (currentRef.current) void restore();
    return () => controller.current?.abort();
  }, []);
  async function run(
    path: string,
    body: Record<string, unknown>,
    userText?: string,
  ) {
    if (locked.current) return false;
    locked.current = true;
    setBusy(true);
    setError("");
    setProgress("正在把这件事捋顺……");
    controller.current = new AbortController();
    const timer = setTimeout(() => controller.current?.abort(), 240000);
    const id = crypto.randomUUID();
    let received = false;
    let added = false;
    try {
      const c = await ensure();
      remember({
        ...c,
        title:
          c.title === "新的问题" && userText ? userText.slice(0, 28) : c.title,
        updated: Date.now(),
      });
      if (userText)
        setMessages((m) => [
          ...m,
          { id: crypto.randomUUID(), role: "user", content: userText },
        ]);
      setMessages((m) => [...m, { id, role: "assistant", content: "" }]);
      added = true;
      await stream(
        path,
        c,
        { ...body, session_id: c.session_id },
        controller.current.signal,
        ({ event, data }) => {
          if (event === "route")
            setProgress(
              `正在看：${((data.intents as string[]) ?? []).map((x) => labels[x] ?? "问题").join(" · ")}`,
            );
          if (event === "tool_start") setProgress("正在核对相关信息……");
          if (event === "tool_end") setProgress("信息核对过了，继续整理。");
          if (event === "retrieval") setProgress("正在查找相关资料……");
          if (event === "need_input")
            setProgress("还差一点资料，补上再往下看。");
          if (event === "interrupt") setProgress("问题已整理好，等你确认。");
          if (event === "token")
            setMessages((m) =>
              m.map((x) =>
                x.id === id
                  ? { ...x, content: x.content + String(data.text ?? "") }
                  : x,
              ),
            );
          if (event === "done") {
            const result = data as unknown as Reply;
            received = true;
            if (currentRef.current)
              remember({
                ...currentRef.current,
                status: result.status,
                summary: result.content.slice(0, 90),
                updated: Date.now(),
              });
            setReply(result);
            // A safety response does not cancel an already pending confirmation.
            if (result.status !== "blocked")
              setInterrupt(result.interrupt ?? null);
            setMessages((m) =>
              m.map((x) =>
                x.id === id
                  ? { ...x, content: result.content, reply: result }
                  : x,
              ),
            );
            setNeedsRecovery(false);
          }
          if (event === "error") {
            if (
              data.code === "STALE_INTERRUPT" ||
              data.code === "RESUME_REQUIRED"
            )
              throw new ApiError(
                409,
                String(data.code),
                "这张确认卡已经过期，正在取回最新问题。",
              );
            if (data.code === "REQUEST_TIMEOUT")
              throw new ApiError(
                504,
                String(data.code),
                "这次整理时间有点长，正在读取会话状态。",
              );
            throw new Error("这次整理没能完成。请先读取会话状态，再继续。");
          }
        },
      );
      return received;
    } catch (e) {
      setNeedsRecovery(true);
      setError(
        controller.current?.signal.aborted
          ? "已停止等待。请先读取会话状态，确认有没有新的结果。"
          : (e as Error).message,
      );
      if (added) setMessages((m) => m.filter((x) => x.id !== id || x.content));
      if (
        e instanceof ApiError &&
        (e.status === 409 || e.status === 504) &&
        currentRef.current
      ) {
        try {
          showSession(
            await api<Session>(
              `/sessions/${currentRef.current.session_id}`,
              currentRef.current,
            ),
          );
        } catch {
          /* retain original error and local partial response */
        }
      }
      return false;
    } finally {
      clearTimeout(timer);
      locked.current = false;
      setBusy(false);
      setProgress("");
      controller.current = null;
    }
  }
  function newSession() {
    if (locked.current) return;
    currentRef.current = null;
    setCurrent(null);
    sessionStorage.removeItem("guanchen.active");
    setMessages([]);
    setReply(null);
    setInterrupt(null);
    setError("");
    setNeedsRecovery(false);
  }
  const send = (message: string, birth_profile?: BirthProfile) =>
    run(
      "/chat/stream",
      { message, new_task: false, ...(birth_profile ? { birth_profile } : {}) },
      message,
    );
  const resume = (
    action: "confirm" | "modify" | "cancel",
    modification?: string,
  ) => {
    if (!interrupt) return Promise.resolve(false);
    return run("/resume/stream", {
      thread_id: interrupt.thread_id,
      confirmation_id: interrupt.confirmation_id,
      action,
      ...(action === "modify" ? { modification } : {}),
    });
  };
  return {
    sessions,
    current,
    messages,
    reply,
    interrupt,
    busy,
    error,
    progress,
    needsRecovery,
    send,
    resume,
    restore,
    newSession,
    ensure,
    stop: () => controller.current?.abort(),
  };
}
