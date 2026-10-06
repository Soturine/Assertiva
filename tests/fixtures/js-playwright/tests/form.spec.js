// No server and no network: every page is set from a string.
const { test, expect } = require("@playwright/test");

const FORM = `<form>
  <label for="email">Email</label><input id="email" placeholder="you@example.com">
  <button type="submit" data-testid="submit">Send</button>
  <p class="hint">We never share it</p>
</form>`;

test.describe("signup form", () => {
  test.beforeEach(async ({ page }) => {
    await page.setContent(FORM);
  });

  test("semantic locators", async ({ page }) => {
    await page.getByLabel("Email").fill("a@b.c");
    await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
    await expect(page.getByPlaceholder("you@example.com")).toHaveValue("a@b.c");
    await expect(page.getByText("We never share it")).toBeVisible();
  });

  test("structural locators", async ({ page }) => {
    await expect(page.getByTestId("submit")).toHaveText("Send");
    await expect(page.locator("p.hint")).toHaveCount(1);
    await expect(page.locator("xpath=//button[@type='submit']")).toBeEnabled();
  });

  test("passes only on retry", async ({ page }, testInfo) => {
    // Deterministically flaky: the first attempt fails (screenshot), the retry passes (trace).
    expect(testInfo.retry).toBe(1);
  });

  test.skip("not ready yet", async () => {});
});
