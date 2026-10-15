import { expect, test } from "@playwright/test";

// End-to-end demo with SYNTHETIC data only.
// Expected PhenoAge (43.6) comes from the independent Decimal reference
// implementation (backend/tests/reference_impl.py) for the converted inputs.
const SHOTS = process.env.E2E_SCREENSHOT_DIR;

const LABS: Array<[string, string, string]> = [
  ["albumin", "4.4", "g/dL"],
  ["creatinine", "0.9", "mg/dL"],
  ["glucose", "92", "mg/dL"],
  ["crp", "0", "mg/L"], // invalid first: CRP 0 cannot be log-transformed
  ["lymphocyte_pct", "31", "%"],
  ["mcv", "89", "fL"],
  ["rdw", "12.9", "%"],
  ["alp", "65", "U/L"],
  ["wbc", "5.8", "10^9/L"],
];

test("new patient -> manual labs -> PhenoAge result -> overview", async ({ page }) => {
  const pseudonym = `SYN-E2E-${Date.now()}`;

  // 1. 新建患者
  await page.goto("/patients/new");
  await page.getByLabel("研究编号（假名）").fill(pseudonym);
  await page.getByLabel("性别").selectOption("female");
  await page.getByLabel(/出生日期/).fill("1974-06-01");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/1-new-patient.png`, fullPage: true });
  await page.getByRole("button", { name: "创建并录入指标" }).click();
  await expect(page).toHaveURL(/\/labs\/new$/);

  // 2. 手工录入指标 (with one invalid value first)
  await page.getByLabel("采样时实际年龄（岁）").fill("52");
  for (const [code, value, unit] of LABS) {
    await page.locator(`#v-${code}`).fill(value);
    await page.locator(`#u-${code}`).selectOption(unit);
  }
  await page.getByRole("button", { name: "保存并计算 PhenoAge" }).click();
  await expect(page.locator(".alert.error")).toContainText("未通过校验");
  await expect(page.getByText(/CRP 为 0 无法进行对数变换/)).toBeVisible();
  await expect(page).toHaveURL(/\/labs\/new$/); // no result produced
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/2a-lab-entry-error.png`, fullPage: true });

  await page.locator("#v-crp").fill("1.5");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/2b-lab-entry.png`, fullPage: true });
  await page.getByRole("button", { name: "保存并计算 PhenoAge" }).click();

  // 3. 计算结果
  await expect(page).toHaveURL(/\/results\//);
  await expect(page.getByTestId("phenoage")).toHaveText("43.6");
  await expect(page.getByText("levine_phenoage_2018 v1.0.0")).toBeVisible();
  await expect(page.getByText(/10\.18632\/aging\.101414/)).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/3-result.png`, fullPage: true });

  // 4. 指标概览
  await page.getByRole("link", { name: "查看指标概览" }).click();
  await expect(page.getByRole("heading", { name: `指标概览 · ${pseudonym}` })).toBeVisible();
  await expect(page.getByText("暂无数据")).toHaveCount(0);
  await expect(page.locator("table").nth(1).locator("tbody tr")).toHaveCount(1);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/4-overview.png`, fullPage: true });
});
