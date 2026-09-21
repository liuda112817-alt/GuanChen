import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUpRight, BookOpen } from "lucide-react";
import type { Citation, Message } from "../api/types";
const labels: Record<string, string> = {
  knowledge: "知识",
  bazi: "八字",
  dream: "梦境",
  liuyao: "六爻",
};
const factLabels: Record<string, string> = {
  bazi: "八字",
  liuyao: "六爻",
  chart: "排盘",
  year_pillar: "年柱",
  month_pillar: "月柱",
  day_pillar: "日柱",
  hour_pillar: "时柱",
  stem: "天干",
  branch: "地支",
  gan_zhi: "干支",
  birth_profile: "出生资料",
  year: "年",
  month: "月",
  day: "日",
  hour: "时",
  minute: "分",
  gender: "性别参数",
  pillars: "四柱",
  five_elements: "五行",
  day_master: "日主",
  hexagram: "卦象",
  name: "名称",
  primary: "本卦",
  changed: "变卦",
  lines: "爻",
  moving_lines: "动爻",
  da_yun: "大运",
  direction: "顺逆",
  start_offset: "起运偏移",
  start_at: "起运时间",
  periods: "大运阶段",
  index: "序号",
  start_year: "起始年",
  start_age: "起始年龄",
  years: "年",
  months: "月",
  days: "日",
  hours: "时",
  hidden_stems: "藏干",
  stem_ten_god: "天干十神",
  ten_god: "十神",
  stem_element: "天干五行",
  branch_element: "地支五行",
  element: "五行",
  calculation_method: "排盘规则",
  library: "历法依据",
  library_version: "历法版本",
  late_zi_sect: "晚子时规则",
  yun_sect: "起运规则",
  time_basis: "时间依据",
  true_solar_time: "真太阳时校正",
  birth_place_affects_calculation: "出生地参与计算",
  casting_method: "起卦方式",
  line_order: "爻序",
  primary_hexagram: "本卦",
  changed_hexagram: "变卦",
  moving_line_positions: "动爻位置",
  coin_tosses: "投掷记录",
  position: "位置",
  coins: "铜钱结果",
  line_value: "爻值",
  value: "爻值",
  polarity: "阴阳",
  moving: "是否动爻",
  heavenly_stem: "天干",
  earthly_branch: "地支",
  six_relative: "六亲",
  six_spirit: "六神",
  is_shi: "世爻",
  is_ying: "应爻",
  upper_trigram: "上卦",
  lower_trigram: "下卦",
};
const factValues: Record<string, string> = {
  system_three_coin: "系统三枚铜钱",
  manual_six_lines: "手动六爻",
  head: "正面",
  tail: "反面",
  true: "是",
  false: "否",
  male: "男",
  female: "女",
  forward: "顺行",
  backward: "逆行",
  yin: "阴",
  yang: "阳",
  heads: "正面",
  tails: "反面",
  three_coins: "三枚铜钱",
  bottom_to_top: "自下而上",
  lunar_python: "公农历换算",
  local_civil_time_as_provided: "用户提供的当地民用时间",
};
function FactValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>未提供</span>;
  if (typeof value === "object")
    return (
      <dl className="facts">
        {Object.entries(value).map(([k, v]) => (
          <div key={k}>
            <dt>
              {factLabels[k] ??
                (/^\d+$/.test(k) ? `第 ${Number(k) + 1} 项` : "资料项")}
            </dt>
            <dd>
              <FactValue value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span>{factValues[String(value)] ?? String(value)}</span>;
}
export function MessageBubble({
  message,
  onCitation,
}: {
  message: Message;
  onCitation: (c: Citation) => void;
}) {
  const r = message.reply;
  return (
    <article
      className={`message ${message.role} ${r?.status === "blocked" ? "safety" : ""}`}
    >
      <div className="message-label">
        {message.role === "assistant" ? (
          <>
            <span className="mini-mark">观</span>观尘{" "}
            <span className="agent-tag">
              {r?.status === "blocked"
                ? "现实支持"
                : r?.used_intents
                    .map((x) => labels[x])
                    .filter(Boolean)
                    .join(" · ")}
            </span>
          </>
        ) : (
          "你"
        )}
      </div>
      <div className="message-body">
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ alt }) => <span>{alt ? `[图片：${alt}]` : "[图片]"}</span>,
            a: ({ children, href }) => (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
                <ArrowUpRight size={13} />
              </a>
            ),
          }}
        >
          {message.content || "正在整理，稍坐一会儿。"}
        </Markdown>
      </div>
      {!!r?.citations.length && (
        <div className="citations">
          {r.citations.map((c) => (
            <button key={c.chunk_id} onClick={() => onCitation(c)}>
              <BookOpen size={13} />
              {c.source_title}
              {c.section ? ` · ${c.section}` : ""}
              <ArrowUpRight size={12} />
            </button>
          ))}
        </div>
      )}
      {r && Object.keys(r.facts ?? {}).length > 0 && (
        <details className="facts-panel">
          <summary>确定事实 · 查看原始资料</summary>
          <FactValue value={r.facts} />
        </details>
      )}
    </article>
  );
}
