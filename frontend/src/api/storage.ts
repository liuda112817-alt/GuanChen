import type { Credential } from "./types";
const key = "guanchen.sessions";
export function loadSessions(): Credential[] {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? "[]");
    return Array.isArray(value)
      ? value.filter(
          (x) =>
            typeof x.session_id === "string" &&
            typeof x.session_token === "string" &&
            typeof x.title === "string" &&
            typeof x.updated === "number",
        )
      : [];
  } catch {
    return [];
  }
}
export function saveSessions(sessions: Credential[]) {
  sessionStorage.setItem(key, JSON.stringify(sessions));
}
export function activeId() {
  return sessionStorage.getItem("guanchen.active");
}
export function setActiveId(id: string) {
  sessionStorage.setItem("guanchen.active", id);
}
