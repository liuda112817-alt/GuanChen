export type Credential = {
  session_id: string;
  session_token: string;
  title: string;
  updated: number;
  status?: Reply["status"];
  summary?: string;
};
export type Citation = {
  chunk_id: string;
  document_id: string;
  source_title: string;
  section: string;
};
export type Interrupt = {
  thread_id: string;
  confirmation_id: string;
  prompt: string;
};
export type BirthProfile = Partial<
  Record<"year" | "month" | "day" | "hour" | "minute", number | null>
> & { gender?: "male" | "female" | null; birth_place_text?: string | null };
export type Reply = {
  session_id: string;
  status:
    | "answered"
    | "needs_input"
    | "interrupted"
    | "cancelled"
    | "blocked"
    | "error";
  content: string;
  used_intents: string[];
  citations: Citation[];
  facts: Record<string, unknown>;
  required_input?: { kind: string; fields: string[] } | null;
  interrupt?: Interrupt | null;
};
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  reply?: Reply;
};
export type Session = {
  messages: { role: string; content: string }[];
  last_response: Reply | null;
  interrupt: Interrupt | null;
};
export type Profile = {
  birth_profile: BirthProfile | null;
  supplied_fields: BirthProfile;
};
export type StreamEvent = { event: string; data: Record<string, unknown> };
