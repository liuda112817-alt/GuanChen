import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const base = {
  session_id: "session-1",
  status: "answered",
  content: "先把事情看清楚，再决定。",
  used_intents: ["knowledge"],
  citations: [],
  facts: {},
  required_input: null,
  interrupt: null,
};
async function mock(page: Page) {
  let last: any = null;
  let messages: any[] = [];
  let profile: any = {};
  let resumes = 0;
  let failure = 0;
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const body = req.postDataJSON();
    if (path.endsWith("/sessions") && req.method() === "POST")
      return route.fulfill({
        status: 201,
        json: { session_id: "session-1", session_token: "secret-test-only" },
      });
    if (req.headers()["authorization"] !== "Bearer secret-test-only")
      return route.fulfill({ status: 401, json: { code: "UNAUTHORIZED" } });
    if (failure) {
      const status = failure;
      failure = 0;
      return route.fulfill({ status, json: { code: "FAILED" } });
    }
    if (path.includes("/citations/"))
      return route.fulfill({
        json: {
          chunk_id: "one",
          document_id: "doc",
          source_title: "原文资料",
          section: "第一章",
          text: "这里是后端返回的原文。",
        },
      });
    if (path.endsWith("/profile")) {
      if (req.method() === "PATCH")
        profile = { ...profile, ...body.birth_profile };
      return route.fulfill({
        json: { birth_profile: null, supplied_fields: profile },
      });
    }
    if (path.endsWith("/session-1"))
      return route.fulfill({
        json: {
          messages,
          last_response: last,
          interrupt: last?.interrupt ?? null,
        },
      });
    if (path.endsWith("/stream")) {
      last = { ...base };
      if (path.includes("/resume/")) {
        resumes++;
        if (body.action === "modify")
          last = {
            ...base,
            status: "interrupted",
            content: "重新确认",
            interrupt: {
              thread_id: "thread",
              confirmation_id: "new-card",
              prompt: body.modification,
            },
          };
        else if (body.action === "cancel")
          last = {
            ...base,
            status: "cancelled",
            content: "已取消，先回到现实看看。",
          };
      } else {
        messages.push({ role: "user", content: body.message });
        if (body.message.includes("八字") && !body.birth_profile)
          last = {
            ...base,
            status: "needs_input",
            content: "请补充出生年。",
            used_intents: ["bazi"],
            required_input: { kind: "birth_profile", fields: ["year"] },
          };
        else if (body.message.includes("换工作"))
          last = {
            ...base,
            status: "interrupted",
            content: "先确认问题。",
            interrupt: {
              thread_id: "thread",
              confirmation_id: "card",
              prompt: "最近三个月，是否考虑换工作？",
            },
          };
        else
          last = {
            ...base,
            content:
              '**先别急。**\n\n<script>alert("xss")</script>\n\n看清再选。',
            citations: [
              {
                chunk_id: "one",
                document_id: "doc",
                source_title: "原文资料",
                section: "第一章",
              },
            ],
          };
      }
      messages.push({ role: "assistant", content: last.content });
      return route.fulfill({
        contentType: "text/event-stream",
        body: `event: route\ndata: {"intents":["knowledge"]}\n\nevent: token\ndata: {"text":"整理好了"}\n\nevent: done\ndata: ${JSON.stringify(last)}\n\n`,
      });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  return {
    resumes: () => resumes,
    fail: (status: number) => {
      failure = status;
    },
  };
}
async function ask(page: Page, text: string) {
  await page.getByLabel("说说你正在面对的事", { exact: true }).fill(text);
  await page.getByRole("button", { name: "发给观尘" }).click();
}
test("home, safe markdown, source, refresh, responsive layout and theme", async ({
  page,
}, info) => {
  await mock(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /今天想/ })).toBeVisible();
  await expect(page.locator(".profile-form")).toHaveCount(0);
  await page.getByRole("button", { name: /读懂一点传统/ }).click();
  await expect(
    page.getByLabel("说说你正在面对的事", { exact: true }),
  ).toHaveValue("正官是什么意思？");
  await page.getByRole("button", { name: "发给观尘" }).click();
  await expect(page.locator(".assistant strong")).toHaveText("先别急。");
  await expect(page.locator(".message script")).toHaveCount(0);
  await page.getByRole("button", { name: /原文资料/ }).click();
  await expect(page.getByText("这里是后端返回的原文。")).toBeVisible();
  await page.getByRole("button", { name: "关闭面板" }).click();
  await page.reload();
  await expect(page.locator(".assistant strong")).toBeVisible();
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(
    "secret-test-only",
  );
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("button", { name: "切换深色" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("birth fields are requested minimally and continue through real contract", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/");
  await ask(page, "我的八字事业如何");
  await expect(page.getByLabel("出生年（公历）")).toBeVisible();
  await expect(page.getByLabel("小时（0–23）")).toHaveCount(0);
  await page.getByLabel("出生年（公历）").fill("1992");
  await page.getByRole("button", { name: "补充资料，继续这个问题" }).click();
  await expect(page.locator(".profile-form")).toHaveCount(0);
});
test("confirmation survives refresh, modification rotates card and cancel does not confirm", async ({
  page,
}) => {
  const m = await mock(page);
  await page.goto("/");
  await ask(page, "我在考虑要不要换工作");
  await expect(page.getByRole("button", { name: "确认起卦" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "修改问题", exact: true }).click();
  await page.getByLabel("你想怎么改？").fill("我想先比较现在的两份工作");
  await page.getByRole("button", { name: "提交修改" }).click();
  await expect(
    page.getByText("我想先比较现在的两份工作", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "先不占" }).click();
  await expect(
    page.getByText("已取消，先回到现实看看。", { exact: true }),
  ).toBeVisible();
  expect(m.resumes()).toBe(2);
});
test("confirm click is submitted once", async ({ page }) => {
  const m = await mock(page);
  await page.goto("/");
  await ask(page, "要不要换工作");
  const button = page.getByRole("button", { name: "确认起卦" });
  await button.evaluate((element: HTMLButtonElement) => {
    element.click();
    element.click();
  });
  await expect(page.locator(".confirmation")).toHaveCount(0);
  expect(m.resumes()).toBe(1);
});
test("HTTP failures preserve draft and allow state recovery", async ({
  page,
}) => {
  const m = await mock(page);
  await page.goto("/");
  await ask(page, "正官是什么意思");
  await expect(page.locator(".assistant")).toHaveCount(1);
  m.fail(422);
  await ask(page, "再解释一下");
  await expect(page.getByRole("alert")).toContainText("资料格式不正确");
  await expect(
    page.getByLabel("说说你正在面对的事", { exact: true }),
  ).toHaveValue("再解释一下");
  await page.getByRole("button", { name: "读取会话状态" }).click();
  await expect(page.getByRole("button", { name: "发给观尘" })).toBeEnabled();
});

for (const [status, copy] of [
  [401, "会话凭证失效"],
  [409, "确认状态已经变化"],
  [504, "这次整理时间有点长"],
] as const) {
  test(`HTTP ${status} has a recovery path without losing credentials`, async ({
    page,
  }) => {
    const m = await mock(page);
    await page.goto("/");
    await ask(page, "正官是什么意思");
    await expect(page.locator(".assistant")).toHaveCount(1);
    m.fail(status);
    await ask(page, "请再解释");
    await expect(page.getByRole("alert")).toContainText(copy);
    expect(
      await page.evaluate(() => sessionStorage.getItem("guanchen.sessions")),
    ).toContain("secret-test-only");
    await page.getByRole("button", { name: "读取会话状态" }).click();
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}
test("SSE errors and truncated streams stop loading and do not auto-resubmit", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/");
  await ask(page, "正官是什么意思");
  await expect(page.locator(".assistant")).toHaveCount(1);
  let requests = 0;
  await page.route("**/chat/stream", async (route) => {
    requests++;
    await route.fulfill({
      contentType: "text/event-stream",
      body: 'event: token\ndata: {"text":"已经收到的一部分"}\n\nevent: error\ndata: {"code":"RUNTIME_ERROR"}\n\n',
    });
  });
  await ask(page, "继续讲讲");
  await expect(page.getByRole("alert")).toContainText("没能完成");
  await expect(
    page.getByText("已经收到的一部分", { exact: true }),
  ).toBeVisible();
  expect(requests).toBe(1);
  await page.getByRole("button", { name: "读取会话状态" }).click();
  await page.route("**/chat/stream", async (route) => {
    await route.fulfill({
      contentType: "text/event-stream",
      body: 'event: token\ndata: {"text":"断线前的片段"}\n\n',
    });
  });
  await ask(page, "再说一点");
  await expect(page.getByRole("alert")).toContainText("连接中断");
  await expect(page.getByText("断线前的片段", { exact: true })).toBeVisible();
});
test("home and guide meet automated WCAG AA checks", async ({ page }, info) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mock(page);
  await page.goto("/");
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("button", { name: "切换深色" }).click();
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "关闭导航", exact: true }).click();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("button", { name: "使用说明", exact: true }).click();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});
