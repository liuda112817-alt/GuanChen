import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  ArrowUp,
  BookOpen,
  ChevronRight,
  Compass,
  History,
  Leaf,
  Menu,
  MessageCircle,
  Moon,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Square,
  Sun,
  UserRound,
  X,
} from "lucide-react";
import { useConversation } from "./hooks/useConversation";
import { api } from "./api/client";
import type { Citation, Profile } from "./api/types";
import { MessageBubble } from "./components/MessageBubble";
import { ProfileForm } from "./components/ProfileForm";
import { Confirmation } from "./components/Confirmation";
type Panel = "history" | "profile" | "guide" | "citation" | null;
const statusLabels: Record<string, string> = {
  answered: "已回复",
  needs_input: "待补充",
  interrupted: "待确认",
  cancelled: "已取消",
  blocked: "现实支持",
  error: "待恢复",
};
const prompts = [
  {
    icon: BookOpen,
    title: "读懂一点传统",
    text: "正官是什么意思？",
    description: "把生涩的词，讲成听得懂的话。",
  },
  {
    icon: Moon,
    title: "聊聊昨晚的梦",
    text: "帮我看看这个梦",
    description: "梦没有标准答案，先听听你的。",
  },
  {
    icon: Compass,
    title: "换个角度看自己",
    text: "我的八字事业如何",
    description: "多一个观察自己的视角。",
  },
  {
    icon: Leaf,
    title: "理一理眼前的事",
    text: "我在考虑要不要换工作",
    description: "先看清，再决定往哪走。",
  },
];
export default function App() {
  const c = useConversation();
  const [draft, setDraft] = useState("");
  const [panel, setPanel] = useState<Panel>(null);
  const [menu, setMenu] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [panelError, setPanelError] = useState("");
  const [panelLoading, setPanelLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [citation, setCitation] = useState<
    (Citation & { text?: string }) | null
  >(null);
  const [dark, setDark] = useState(() => {
    try {
      return localStorage.getItem("guanchen.theme")
        ? localStorage.getItem("guanchen.theme") === "dark"
        : matchMedia("(prefers-color-scheme: dark)").matches;
    } catch {
      return false;
    }
  });
  const scroll = useRef<HTMLDivElement>(null);
  const bottom = useRef(true);
  const input = useRef<HTMLTextAreaElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const generation = useRef(0);
  const [away, setAway] = useState(false);
  useEffect(() => {
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape" && menu) {
        setMenu(false);
        document.getElementById("nav-toggle")?.focus();
      }
    };
    window.addEventListener("keydown", dismiss);
    return () => window.removeEventListener("keydown", dismiss);
  }, [menu]);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const change = () => {
      if (!localStorage.getItem("guanchen.theme")) setDark(media.matches);
    };
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    if (bottom.current && c.messages.length)
      scroll.current?.scrollTo({
        top: scroll.current.scrollHeight,
        behavior: "instant",
      });
  }, [c.messages, c.progress, c.interrupt]);
  useEffect(() => {
    if (panel) dialog.current?.showModal();
    else dialog.current?.close();
  }, [panel]);
  const closePanel = () => {
    generation.current++;
    setPanel(null);
  };
  async function openPanel(next: Panel) {
    setMenu(false);
    setPanelError("");
    setNotice("");
    setProfile(null);
    setPanel(next);
    const gen = ++generation.current;
    if (next === "profile") {
      setPanelLoading(true);
      try {
        const session = await c.ensure();
        const p = await api<Profile>(
          `/sessions/${session.session_id}/profile`,
          session,
        );
        if (gen === generation.current) setProfile(p);
      } catch (e) {
        if (gen === generation.current) setPanelError((e as Error).message);
      } finally {
        if (gen === generation.current) setPanelLoading(false);
      }
    } else setPanelLoading(false);
  }
  async function openCitation(value: Citation) {
    setCitation(value);
    setPanel("citation");
    setPanelLoading(true);
    setPanelError("");
    const gen = ++generation.current;
    try {
      if (!c.current) throw new Error("请先恢复会话。");
      const result = await api<Citation & { text: string }>(
        `/sessions/${c.current.session_id}/citations/${encodeURIComponent(value.chunk_id)}`,
        c.current,
      );
      if (gen === generation.current) setCitation(result);
    } catch (e) {
      if (gen === generation.current)
        setPanelError(
          (e as { status?: number }).status === 404
            ? "这条资料已经不在当前回答里了。"
            : (e as Error).message,
        );
    } finally {
      if (gen === generation.current) setPanelLoading(false);
    }
  }
  async function send() {
    const text = draft.trim();
    if (!text || c.busy || c.interrupt || c.needsRecovery) return;
    setDraft("");
    bottom.current = true;
    const success = await c.send(text);
    if (!success) setDraft(text);
  }
  function newQuestion() {
    c.newSession();
    setDraft("");
    setMenu(false);
    closePanel();
    bottom.current = true;
    input.current?.focus();
  }
  return (
    <div className="app-shell">
      {menu && (
        <button
          className="nav-scrim"
          aria-label="关闭导航"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            if (!c.busy) newQuestion();
          }}
        >
          <img src="/favicon.svg" alt="" />
          <span>
            观尘<small>把复杂的事，先看清楚。</small>
          </span>
        </a>
        <button
          className="new-question"
          onClick={newQuestion}
          disabled={c.busy}
        >
          <Plus size={18} />
          新问题<span>开始聊聊</span>
        </button>
        <nav aria-label="主导航">
          <button
            className="nav-item active"
            onClick={() => {
              closePanel();
              setMenu(false);
            }}
          >
            <MessageCircle size={18} />
            与观尘聊聊
            <span className="nav-dot" />
          </button>
          <button
            className="nav-item"
            onClick={() => void openPanel("history")}
            disabled={c.busy}
          >
            <History size={18} />
            历史会话
          </button>
          <button
            className="nav-item"
            onClick={() => void openPanel("profile")}
            disabled={c.busy}
          >
            <UserRound size={18} />
            我的资料
          </button>
        </nav>
        <div className="recent-heading">最近聊过</div>
        <div className="recent-list">
          {c.sessions.slice(0, 5).map((s) => (
            <button
              key={s.session_id}
              disabled={c.busy}
              className={
                s.session_id === c.current?.session_id ? "selected" : ""
              }
              onClick={() => {
                setMenu(false);
                setDraft("");
                void c.restore(s);
              }}
            >
              <span>{s.title}</span>
              <ChevronRight size={13} />
            </button>
          ))}
          {!c.sessions.length && (
            <p>
              还没有故事。
              <br />
              从眼前这件小事开始吧。
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="side-note">
            <Leaf size={17} />
            <p>
              看清是为了更自在，
              <br />
              不是给自己多一道束缚。
            </p>
          </div>
          <button className="nav-item" onClick={() => void openPanel("guide")}>
            <BookOpen size={17} />
            使用说明
            <ArrowUpRight size={14} />
          </button>
          <button
            className="nav-item theme-button"
            onClick={() => {
              setDark(!dark);
              localStorage.setItem("guanchen.theme", dark ? "light" : "dark");
            }}
          >
            {dark ? <Sun size={17} /> : <Moon size={17} />}
            <span>{dark ? "切换浅色" : "切换深色"}</span>
            <span className="theme-swatch" />
          </button>
          <div className="sidebar-footer">
            观尘 <span>留一点从容给自己</span>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-only"
              aria-label="打开导航"
              id="nav-toggle"
              onClick={() => setMenu(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">一处安静的思考空间</span>
          </div>
          <button className="top-guide" onClick={() => void openPanel("guide")}>
            <span className="status-dot" />
            慢慢说，我们一起看
            <ArrowUpRight size={14} />
          </button>
        </header>
        <div className="workspace">
          <div className="conversation-column">
            <div
              className="conversation-scroll"
              ref={scroll}
              onScroll={() => {
                const el = scroll.current!;
                bottom.current =
                  el.scrollHeight - el.scrollTop - el.clientHeight < 100;
                setAway(!bottom.current);
              }}
            >
              {!c.messages.length ? (
                <section className="welcome">
                  <div className="welcome-kicker">
                    <span />观 · 照见当下
                  </div>
                  <h1>
                    纷扰先放一放。
                    <br />
                    今天想<span>看清楚</span>什么？
                  </h1>
                  <p className="welcome-copy">
                    可以问传统文化，也可以直接说你的现实困惑。
                    <br />
                    别急，咱们一层层看。
                  </p>
                  <div className="prompt-grid">
                    {prompts.map(
                      ({ icon: Icon, title, text, description }, i) => (
                        <button
                          className="prompt-card"
                          key={title}
                          onClick={() => {
                            setDraft(text);
                            input.current?.focus();
                          }}
                          disabled={c.busy}
                        >
                          <span className={`prompt-icon tone-${i}`}>
                            <Icon size={21} />
                          </span>
                          <ArrowUpRight className="prompt-arrow" size={17} />
                          <h2>{title}</h2>
                          <p>{description}</p>
                        </button>
                      ),
                    )}
                  </div>
                  <div className="welcome-foot">
                    <span />
                    不急着给答案，先把问题看明白。
                    <span />
                  </div>
                </section>
              ) : (
                <div className="messages">
                  {c.messages.map((m) => (
                    <MessageBubble
                      key={m.id}
                      message={m}
                      onCitation={(v) => void openCitation(v)}
                    />
                  ))}
                  {c.busy && (
                    <div className="progress" role="status">
                      <span className="status-dot" />
                      {c.progress || "正在恢复会话……"}
                    </div>
                  )}
                  {c.interrupt && (
                    <Confirmation
                      key={c.interrupt.confirmation_id}
                      value={c.interrupt}
                      busy={c.busy || c.needsRecovery}
                      submit={c.resume}
                    />
                  )}{" "}
                  {c.reply?.status === "needs_input" &&
                    c.reply.required_input?.kind === "birth_profile" &&
                    !c.interrupt && (
                      <section className="input-card">
                        <span className="eyebrow">还差一点资料</span>
                        <h3>补上这些，再往下看。</h3>
                        <ProfileForm
                          fields={c.reply.required_input.fields}
                          busy={c.busy || c.needsRecovery}
                          label="补充资料，继续这个问题"
                          submit={async (values) => {
                            await c.send(
                              "已补充出生资料，请继续刚才的问题。",
                              values,
                            );
                          }}
                        />
                      </section>
                    )}
                </div>
              )}
            </div>
            <div className="composer-area">
              {away && (
                <button
                  className="jump-button"
                  onClick={() => {
                    bottom.current = true;
                    scroll.current?.scrollTo({
                      top: scroll.current.scrollHeight,
                      behavior: "smooth",
                    });
                  }}
                >
                  <ArrowDown size={14} />
                  回到最新
                </button>
              )}
              {c.error && (
                <div className="error-box" role="alert">
                  <p>{c.error}</p>
                  <div className="button-row">
                    <button
                      className="quiet"
                      disabled={c.busy}
                      onClick={() => void c.restore()}
                    >
                      <RefreshCw size={14} />
                      读取会话状态
                    </button>
                    <button
                      className="quiet"
                      disabled={c.busy}
                      onClick={newQuestion}
                    >
                      新问题
                    </button>
                  </div>
                </div>
              )}
              <div className="composer">
                <label className="sr-only" htmlFor="question">
                  说说你正在面对的事
                </label>
                <textarea
                  id="question"
                  ref={input}
                  maxLength={12000}
                  placeholder={
                    c.interrupt
                      ? "先确认或修改上面的问题，再往下聊。"
                      : "说说你正在面对的事……"
                  }
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing &&
                      matchMedia("(pointer: fine)").matches
                    ) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                />
                <div className="composer-bottom">
                  <span>
                    <span className="composer-dot" />
                    {c.interrupt
                      ? "六爻确认中"
                      : c.reply?.required_input?.kind === "birth_profile"
                        ? "八字资料待补充"
                        : "自然表达就好"}
                    <span className="keyboard-hint">
                      Enter 发送 · Shift + Enter 换行
                    </span>
                  </span>
                  {c.busy ? (
                    <button className="send-button" onClick={c.stop}>
                      <Square size={13} />
                      停止等待
                    </button>
                  ) : (
                    <button
                      className="send-button"
                      disabled={
                        !draft.trim() || !!c.interrupt || c.needsRecovery
                      }
                      onClick={() => void send()}
                    >
                      发给观尘
                      <ArrowUp size={16} />
                    </button>
                  )}
                </div>
              </div>
              <p className="composer-disclaimer">
                传统文化提供观察角度，现实选择仍由你做主。
              </p>
            </div>
          </div>
          <aside className="context" tabIndex={0} aria-label="使用提示">
            <div className="context-heading">
              <span>此刻 · 不必着急</span>
              <Settings2 size={16} />
            </div>
            <div className="landscape" aria-hidden="true">
              <div className="sun" />
              <div className="mountain back" />
              <div className="mountain front" />
              <div className="landscape-line" />
              <span>观自在</span>
            </div>
            <h2>
              事缓则圆。
              <br />
              心定，路就清楚一点。
            </h2>
            <p>
              问题不必一次说完整。
              <br />
              先从最在意的那一点开始。
            </p>
            <div className="context-divider" />
            <span className="eyebrow">我们可以这样聊</span>
            <ol>
              <li>
                <span>01</span>
                <div>
                  先说眼前的事<small>一个疑问，一场梦，一个选择。</small>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  一起换个角度<small>有依据，也给不确定留点空间。</small>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  把脚步放回现实<small>从一个能做到的小行动开始。</small>
                </div>
              </li>
            </ol>
            <div className="privacy-note">
              <ShieldCheck size={17} />
              <span>
                无需注册即可开始。
                <br />
                会话凭证仅保留在当前标签页。
              </span>
            </div>
          </aside>
        </div>
      </main>
      <dialog
        ref={dialog}
        className="drawer"
        aria-labelledby="drawer-title"
        onCancel={closePanel}
        onClick={(e) => {
          if (e.target === dialog.current) closePanel();
        }}
      >
        <div className="drawer-content">
          <header>
            <div>
              <span className="eyebrow">观尘 · 慢慢看</span>
              <h2 id="drawer-title">
                {panel === "history"
                  ? "聊过的那些事"
                  : panel === "profile"
                    ? "出生资料"
                    : panel === "citation"
                      ? "看看原文"
                      : "和观尘怎么聊"}
              </h2>
            </div>
            <button
              className="icon-button"
              aria-label="关闭面板"
              onClick={closePanel}
            >
              <X size={20} />
            </button>
          </header>
          {panelLoading && <p role="status">正在取回资料……</p>}
          {panelError && (
            <div className="error-box" role="alert">
              {panelError}
              <button
                className="quiet"
                onClick={() =>
                  panel === "citation" && citation
                    ? void openCitation(citation)
                    : void openPanel(panel)
                }
              >
                重新加载
              </button>
            </div>
          )}
          {panel === "history" && (
            <>
              <p className="muted">
                这里保存当前标签页里的会话入口。刷新可以恢复，关闭标签页后将无法凭此入口找回。
              </p>
              {!c.sessions.length ? (
                <div className="empty-panel">
                  还没有聊过的事。
                  <button className="primary" onClick={newQuestion}>
                    开始一个新问题
                  </button>
                </div>
              ) : (
                c.sessions.map((s) => (
                  <button
                    className="history-item"
                    key={s.session_id}
                    disabled={c.busy}
                    onClick={() => {
                      closePanel();
                      setDraft("");
                      void c.restore(s);
                    }}
                  >
                    <MessageCircle size={18} />
                    <span>
                      {s.title}
                      <small>
                        {new Date(s.updated).toLocaleString("zh-CN")} ·{" "}
                        {statusLabels[s.status ?? ""] ?? "未开始"}
                      </small>
                      {s.summary && <small>{s.summary}</small>}
                    </span>
                    <ChevronRight size={17} />
                  </button>
                ))
              )}
            </>
          )}
          {panel === "profile" && profile && (
            <>
              <p className="muted">
                只用于需要它的八字问题。资料按当前会话保存，你可以随时更正；不会给你贴上命运标签。
              </p>
              <ProfileForm
                initial={{
                  ...profile.birth_profile,
                  ...profile.supplied_fields,
                }}
                busy={c.busy}
                submit={async (birth_profile) => {
                  const session = await c.ensure();
                  setProfile(
                    await api<Profile>("/profile", session, "PATCH", {
                      session_id: session.session_id,
                      birth_profile,
                    }),
                  );
                  setNotice("资料已保存，可以回去继续聊了。");
                }}
              />
              {notice && (
                <p role="status" className="success-text">
                  {notice}
                </p>
              )}
            </>
          )}
          {panel === "citation" && citation && !panelLoading && !panelError && (
            <>
              <div className="source-label">
                <BookOpen size={15} />
                来源原文
              </div>
              <h3>{citation.source_title}</h3>
              <p className="muted">{citation.section}</p>
              <blockquote className="source-text">{citation.text}</blockquote>
              <p className="muted small">
                以上为来源原文，与观尘的解释分开展示。
              </p>
            </>
          )}
          {panel === "guide" && (
            <>
              <p className="muted">
                观尘陪你把事情看清一点。传统文化是一扇窗，生活的方向盘在你手里。
              </p>
              {[
                [
                  "先问问题",
                  "知识、梦境、八字和现实决策，都可以从自然语言开始。不需要想好怎么问。",
                ],
                [
                  "需要时补资料",
                  "只有八字真正需要时，才会请你填写出生资料。不确定的资料可以先不填。",
                ],
                [
                  "回到现实做选择",
                  "六爻确认后才会起卦，你也可以修改或取消。涉及健康、法律和投资，请结合专业意见。",
                ],
              ].map(([title, text], i) => (
                <section className="guide-card" key={title}>
                  <span>0{i + 1}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </section>
              ))}
              <p className="muted small">
                回答由人工智能生成，可能存在遗漏或错误。引用可打开原文核对。会话内容和主动提供的资料会发送到服务端处理；关闭标签页只移除浏览器中的会话入口，并不代表删除服务端记录。
              </p>
            </>
          )}
        </div>
      </dialog>
    </div>
  );
}
