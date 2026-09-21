import { test, expect } from "@playwright/test";
test.skip(
  process.env.GUANCHEN_REAL_E2E !== "1",
  "Opt-in: requires running API, PostgreSQL, corpus and provider credentials.",
);
test("real browser → Vite proxy → FastAPI → PostgreSQL/provider", async ({
  page,
}, info) => {
  test.setTimeout(600000);
  await page.goto("/");
  await page.screenshot({
    path: `../reports/frontend-${info.project.name}-home.png`,
    fullPage: true,
  });
  const input = page.getByLabel("说说你正在面对的事", { exact: true });
  async function send(text: string) {
    await input.fill(text);
    await page.getByRole("button", { name: "发给观尘" }).click();
    await expect(page.getByRole("button", { name: "停止等待" })).toHaveCount(
      0,
      { timeout: 240000 },
    );
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  await send("正官是什么意思？");
  await expect(page.locator(".assistant").last()).toContainText("正官");
  const sources = page.locator(".citations button");
  expect(await sources.count()).toBeGreaterThan(0);
  await sources.first().click();
  await expect(page.locator(".source-text")).not.toBeEmpty();
  await page.getByRole("button", { name: "关闭面板" }).click();
  await page.screenshot({
    path: `../reports/frontend-${info.project.name}-answer.png`,
    fullPage: true,
  });
  await page.reload();
  await expect(page.locator(".assistant").last()).toContainText("正官", {
    timeout: 20000,
  });
  await send(
    "我昨晚梦见在学校迷路，找不到教室，有点着急，这个梦可以怎么理解？",
  );
  await expect(page.locator(".profile-form")).toHaveCount(0);
  await send("请用八字帮我看看事业。");
  await expect(page.locator(".profile-form")).toBeVisible();
  await page.getByLabel("出生年（公历）").fill("1992");
  await page.getByLabel("月", { exact: true }).fill("8");
  await page.getByLabel("日", { exact: true }).fill("15");
  await page.getByLabel("小时（0–23）").fill("10");
  await page.getByLabel("分钟", { exact: true }).fill("30");
  await page.getByLabel("排盘性别参数").selectOption("male");
  await page.getByRole("button", { name: "补充资料，继续这个问题" }).click();
  await expect(page.getByRole("button", { name: "停止等待" })).toHaveCount(0, {
    timeout: 240000,
  });
  await expect(page.locator(".profile-form")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await send(
    "请用六爻帮我看看：未来三个月，我是否适合从目前的工作转到已经拿到录用通知的新公司？",
  );
  await expect(page.getByRole("button", { name: "确认起卦" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "确认起卦" })).toBeVisible({
    timeout: 20000,
  });
  await page.getByRole("button", { name: "先不占" }).click();
  await expect(page.locator(".confirmation")).toHaveCount(0, {
    timeout: 240000,
  });
  await expect(page.getByRole("alert")).toHaveCount(0);
});
