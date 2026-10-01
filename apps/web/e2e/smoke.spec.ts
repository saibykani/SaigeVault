import { expect, test } from "@playwright/test";

const PAGES = [
  { path: "/", heading: "Dashboard" },
  { path: "/files", heading: "Files" },
  { path: "/search", heading: "Search" },
  { path: "/collections", heading: "Collections" },
  { path: "/ask", heading: "Ask Saige" },
  { path: "/timeline", heading: "Timeline" },
  { path: "/settings", heading: "Settings" },
  { path: "/system", heading: "System status" },
  { path: "/login", heading: "Sign in to your vault" },
];

for (const { path, heading } of PAGES) {
  test(`${path} renders its heading`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  });
}

test("security headers are set on pages", async ({ request }) => {
  const response = await request.get("/");
  const headers = response.headers();
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-powered-by"]).toBeUndefined();
});

test("unknown routes show the not-found page", async ({ page }) => {
  const response = await page.goto("/definitely-not-a-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test.describe("desktop", () => {
  test.skip(({ isMobile }) => isMobile, "desktop-only interactions");

  test("command palette opens with Ctrl+K and navigates", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("ControlOrMeta+k");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder(/type a command/i).fill("collections");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/collections$/);
    await expect(dialog).toBeHidden();
  });

  test("sidebar navigation marks the active page", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("complementary", { name: "Main navigation" });
    await nav.getByRole("link", { name: /Files/ }).click();
    await expect(page).toHaveURL(/\/files$/);
    await expect(nav.getByRole("link", { name: /Files/ })).toHaveAttribute("aria-current", "page");
  });

  test("theme can be switched to dark", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("radiogroup", { name: "Theme" })
      .getByRole("radio", { name: "Dark" })
      .click();
    await expect(page.locator("html")).toHaveClass(/dark/);
  });

  test("dropping a file does not upload it while uploads are unavailable", async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (r) => {
      if (r.method() !== "GET") requests.push(r.url());
    });
    await page.goto("/files");
    // aria-disabled (not disabled): announced as unavailable, but still clickable
    // so it can explain why. Playwright treats aria-disabled as non-actionable.
    await page.getByRole("button", { name: "Upload", exact: true }).click({ force: true });
    await expect(page.getByText(/Uploads arrive in Phase/)).toBeVisible();
    expect(requests).toEqual([]);
  });
});

test.describe("mobile", () => {
  test.skip(({ isMobile }) => !isMobile, "mobile-only layout");

  test("bottom navigation is visible", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav).toBeVisible();
    await nav.getByRole("link", { name: "Search" }).click();
    await expect(page).toHaveURL(/\/search$/);
  });
});
