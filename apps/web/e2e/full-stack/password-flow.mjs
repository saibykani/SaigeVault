// Browser walk-through of email + password sign-in with two-step verification.
// Needs the fake stack (tests/e2e/fake_stack.py) on :8010 and the web app on :3101.
import { createHmac } from "node:crypto";

import { chromium } from "@playwright/test";

const BASE = "http://localhost:3101";
const out = process.argv[2] ?? "test-results";
const log = (...a) => console.log("✔", ...a);

function totp(secret, offsetSteps = 0) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/=+$/, ""))
    bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const step = Math.floor(Date.now() / 1000 / 30) + offsetSteps;
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(step));
  const mac = createHmac("sha1", key).update(msg).digest();
  const o = mac[mac.length - 1] & 0x0f;
  return String((mac.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

const email = `pw-${Date.now()}@example.com`;
const password = "plum orbit kettle 47";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
page.on("pageerror", (e) => console.error("pageerror", e.message));

await page.goto(`${BASE}/login`);
await page.getByRole("button", { name: "Create an account" }).click();
await page.locator("#pw-name").fill("E2E Tester");
await page.locator("#pw-email").fill(email);
await page.getByLabel("Password", { exact: true }).fill("short");
await page.screenshot({ path: `${out}/pw-01-register.png` });
await page.getByLabel("Password", { exact: true }).fill(password);
await page.getByRole("button", { name: "Create account" }).click();
await page.waitForURL((u) => !u.pathname.startsWith("/login"));
log("registered and signed in", email);

await page.goto(`${BASE}/settings#security`);
await page.getByRole("button", { name: "Turn on" }).click();
await page.getByLabel("Password", { exact: true }).fill(password);
await page.getByRole("button", { name: "Continue" }).click();
const qr = page.getByRole("img", { name: "Authenticator setup QR code" });
await qr.waitFor();
const secret = (await page.locator("code").first().textContent()).trim();
await page.screenshot({ path: `${out}/pw-02-totp-qr.png` });
await page.getByLabel("6-digit code").fill(totp(secret, -1));
await page.getByRole("button", { name: "Turn on" }).last().click();
await page.getByText("They won't be shown again").waitFor();
const recovery = await page.locator("ul.font-mono li").allTextContents();
if (recovery.length !== 10) throw new Error(`expected 10 recovery codes, got ${recovery.length}`);
await page.screenshot({ path: `${out}/pw-03-recovery.png` });
await page.getByRole("button", { name: "I've saved them" }).click();
await page.getByText("recovery codes left").waitFor();
await page.screenshot({ path: `${out}/pw-04-security.png` });
log("two-step verification on");

// Sign out via the API, then sign back in through the UI.
await page.evaluate(async () => {
  const csrf = document.cookie.match(/saige_csrf=([^;]+)/)?.[1] ?? "";
  await fetch("/api/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrf } });
});
await page.goto(`${BASE}/login?next=/files`);
await page.locator("#pw-email").fill(email);
await page.getByLabel("Password", { exact: true }).fill("wrong password here");
await page
  .locator("#pw-email")
  .locator("xpath=ancestor::form")
  .getByRole("button", { name: "Sign in", exact: true })
  .click();
await page.getByText("Email or password is incorrect.").waitFor();
log("wrong password rejected");
await page.getByLabel("Password", { exact: true }).fill(password);
await page
  .locator("#pw-email")
  .locator("xpath=ancestor::form")
  .getByRole("button", { name: "Sign in", exact: true })
  .click();
await page.getByText("Two-step verification").waitFor();
await page.screenshot({ path: `${out}/pw-05-mfa.png` });
await page.getByLabel("Verification code").fill("000000");
await page.getByRole("button", { name: "Verify" }).click();
await page.getByText("That code isn't valid").waitFor();
await page.getByLabel("Verification code").fill(totp(secret));
await page.getByRole("button", { name: "Verify" }).click();
await page.waitForURL(`${BASE}/files`);
log("signed in with password + authenticator code");

await browser.close();
console.log("PASSWORD FLOW PASSED");
