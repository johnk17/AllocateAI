import { test, expect } from "@playwright/test";
async function login(page) {
  await page.goto("/");
  await page
    .getByLabel("Email", { exact: true })
    .fill(process.env.ADMIN_EMAIL || "admin@allocate.local");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.ADMIN_PASSWORD || "LocalAdmin@12345");
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Manage internships and allocations.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Allocation readiness" }),
  ).toBeVisible();
  await expect(page.getByRole('button', {name:'Refresh workspace',exact:true})).toBeEnabled();
}

test("Next.js dashboard shows real input readiness and explicit fixture mode", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByText("Fixture mode · no live LLM", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Workspace status" }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("overview.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("Skills Explorer retains distinct names, source provenance and real listing demand", async ({
  page,
}, testInfo) => {
  await login(page);
  await page
    .getByRole("button", { name: "Skills Explorer", exact: true })
    .click();
  await page.getByLabel("Search skills", { exact: true }).fill("JavaScript");
  await expect(
    page.locator('tbody td strong').filter({hasText:/^JavaScript$/}).first(),
  ).toBeVisible();
  await expect(
    page.locator('tbody td strong').filter({hasText:/^Java$/}),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Demand in Imported Listings", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Demand measured from this workspace" }),
  ).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("skills.png"), fullPage: true });
});
test("Policy citations and no-answer abstention use the real historical corpus; mobile fits", async ({
  page,
}, testInfo) => {
  await login(page);
  await page
    .getByRole("button", { name: "Policy Evidence", exact: true })
    .click();
  const selector = page.getByRole("combobox", { name: "Policy search version" });
  const historical = selector.locator("option").filter({ hasText: "Historical public-reference retrieval benchmark" });
  if ((await historical.count()) === 0) {
    test.skip(
      true,
      "Import a dated public corpus before policy browser evaluation",
    );
    return;
  }
  await selector.selectOption(await historical.getAttribute("value"));
  await page
    .getByLabel("Policy question", { exact: true })
    .fill("What is the one-time grant for incidentals?");
  await page
    .getByRole("button", { name: "Search policy evidence", exact: true })
    .click();
  await expect(
    page.getByText("Extractive supporting passage", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".policy-answer a").first()).toHaveAttribute(
    "href",
    /pib.gov.in/,
  );
  await page.screenshot({ path: testInfo.outputPath("policy.png"), fullPage: true });
  await page
    .getByLabel("Policy question", { exact: true })
    .fill("Which employer guarantees me a confirmed job offer tomorrow?");
  await page
    .getByRole("button", { name: "Search policy evidence", exact: true })
    .click();
  await expect(
    page.getByText(
      "Policy evidence was insufficient to answer this question.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .getByRole("button", { name: "Agent Activity", exact: true })
    .click();
  await expect.poll(async()=>page.locator('.sidebar').evaluate(el=>Math.round(el.getBoundingClientRect().right))).toBeLessThanOrEqual(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("mobile.png"), fullPage: true });
});
