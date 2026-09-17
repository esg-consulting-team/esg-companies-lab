import { expect, test } from "@playwright/test";

function trackConsoleErrors(page) {
  const errors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));
  return errors;
}

test.describe("공통 셸", () => {
  test("L1 접속 시 브랜드/기업 셀렉터/레일이 보인다", async ({ page }) => {
    const errors = trackConsoleErrors(page);
    await page.goto("/l1");
    await expect(page.getByText("ESG 진단 콘솔")).toBeVisible();
    await expect(page.locator(".rail-item.active")).toHaveText(/L1/);
    await expect(page.getByTestId("company-select")).not.toHaveValue("");
    expect(errors).toEqual([]);
  });
});

test.describe("L1 종합 현황", () => {
  test("KPI와 손실점수 Top5가 로드된다", async ({ page }) => {
    await page.goto("/l1");
    await expect(page.getByText("손실점수 Top 5")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("즉시 착수 과제")).toBeVisible();
  });

  test("손실점수 Top5 클릭 시 L3로 이동한다", async ({ page }) => {
    await page.goto("/l1");
    await expect(page.getByText("손실점수 Top 5")).toBeVisible({ timeout: 15000 });
    await page.getByTestId("gap-top-row").first().click();
    await expect(page).toHaveURL(/\/l3\?item=/);
  });
});

test.describe("L2 영역별 진단", () => {
  test("히트맵이 로드되고 클릭 시 L3로 이동한다", async ({ page }) => {
    await page.goto("/l2");
    await expect(page.getByText("항목 히트맵")).toBeVisible({ timeout: 15000 });
    await page.locator(".heat-cell").first().click();
    await expect(page).toHaveURL(/\/l3\?item=/);
  });
});

test.describe("L3 항목 상세", () => {
  test("항목 헤더와 해결방안(또는 서술형 narrative) 블록이 보인다", async ({ page }) => {
    await page.goto("/l3");
    await expect(page.locator(".item-header")).toBeVisible({ timeout: 15000 });
    // narrative 데이터가 있는 항목은 "진단 결과 서술" 3분할 카드로, 없으면 기존 "해결방안" 3분할로 표시된다.
    await expect(page.getByText(/진단 결과 서술|해결방안/).first()).toBeVisible();
  });
});

test.describe("L4~L7 스모크 테스트", () => {
  for (const path of ["/l4", "/l5", "/l6", "/l7"]) {
    test(`${path} 콘솔 에러 없이 로드된다`, async ({ page }) => {
      const errors = trackConsoleErrors(page);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      expect(errors).toEqual([]);
    });
  }
});

test.describe("기업 전환", () => {
  test("셀렉터로 하나마이크론으로 전환할 수 있다", async ({ page }) => {
    await page.goto("/l1");
    await page.getByTestId("company-select").selectOption({ value: "하나마이크론" });
    await expect(page.getByTestId("company-select")).toHaveValue("하나마이크론");
    await expect(page.getByText("손실점수 Top 5")).toBeVisible({ timeout: 15000 });
  });
});

test.describe("L5 점수 시뮬레이터", () => {
  test("과제 체크 시 서버에서 재계산된 결과가 표시된다", async ({ page }) => {
    await page.goto("/l5");
    await expect(page.getByText("4개년 실행 로드맵")).toBeVisible({ timeout: 15000 });
    await page.locator(".sim-task-row input[type=checkbox]").first().check();
    await expect(page.locator(".sim-result-box")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".sim-result-value")).toContainText("→");
  });
});

test.describe("L7 리포트", () => {
  test("XLSX 내보내기가 실제 파일을 다운로드한다", async ({ page }) => {
    await page.goto("/l7");
    await expect(page.getByText("포함 섹션")).toBeVisible({ timeout: 15000 });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "리포트 생성" }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
  });
});
