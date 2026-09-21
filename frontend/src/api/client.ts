import { readSSE } from "./sse";
import type { Credential, StreamEvent } from "./types";
const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
const messages: Record<number, string> = {
  401: "会话凭证失效，请重新开始一个会话。",
  409: "确认状态已经变化，请读取最新会话。",
  422: "资料格式不正确，请检查日期、时间和必填项。",
  429: "问得有点快，稍等一下再试。",
  504: "这次整理时间有点长，请先读取会话状态再继续。",
};
async function request(
  path: string,
  session: Credential | null,
  method = "GET",
  payload?: unknown,
  signal?: AbortSignal,
) {
  let response: Response;
  try {
    response = await fetch(`${base}/api/v1${path}`, {
      method,
      headers: {
        ...(method === "POST" && session ? { "Idempotency-Key": crypto.randomUUID() } : {}),
        ...(payload ? { "Content-Type": "application/json" } : {}),
        ...(session
          ? { Authorization: `Bearer ${session.session_token}` }
          : {}),
      },
      body: payload ? JSON.stringify(payload) : undefined,
      signal: signal ?? AbortSignal.timeout(20000),
      cache: "no-store",
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("暂时没连上观尘。请检查网络，稍后再试。");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.code ?? "REQUEST_FAILED",
      messages[response.status] ?? "这次没能完成，请稍后再试。",
    );
  }
  return response;
}
export async function api<T>(
  path: string,
  session: Credential | null = null,
  method = "GET",
  payload?: unknown,
): Promise<T> {
  return (await request(path, session, method, payload)).json();
}
export async function stream(
  path: string,
  session: Credential,
  payload: unknown,
  signal: AbortSignal,
  onEvent: (e: StreamEvent) => void,
) {
  const response = await request(path, session, "POST", payload, signal);
  if (
    !response.body ||
    !response.headers.get("content-type")?.includes("text/event-stream")
  )
    throw new Error("服务返回异常，请读取会话状态。");
  await readSSE(response.body, onEvent);
}
