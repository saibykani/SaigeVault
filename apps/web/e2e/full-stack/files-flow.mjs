import { deflateSync } from "node:zlib";

import { chromium } from "@playwright/test";

const BASE = "http://localhost:3101";
const out = process.argv[2] ?? "test-results";
const log = (...a) => console.log("✔", ...a);

// A real, minimal multi-page PDF with a correct xref table.
function makePdf(pages) {
  const objects = [];
  const kids = pages.map((_, i) => `${3 + i * 2} 0 R`).join(" ");
  objects.push("<< /Type /Catalog /Pages 2 0 R >>");
  objects.push(`<< /Type /Pages /Kids [${kids}] /Count ${pages.length} >>`);
  pages.forEach((text, i) => {
    const stream = `BT /F1 24 Tf 72 720 Td (${text}) Tj ET`;
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents ${4 + i * 2} 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>`,
    );
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  });
  let body = "%PDF-1.4\n";
  const offsets = [];
  objects.forEach((obj, i) => {
    offsets.push(body.length);
    body += `${i + 1} 0 obj\n${obj}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const o of offsets) body += `${String(o).padStart(10, "0")} 00000 n \n`;
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}

function makePng() {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const c = Buffer.alloc(4);
    c.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, c]);
  };
  const w = 120,
    h = 80;
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const o = y * (w * 3 + 1) + 1 + x * 3;
      raw[o] = 61;
      raw[o + 1] = 122 + (x % 40);
      raw[o + 2] = 99;
    }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const consoleErrors = [];
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
page.on("pageerror", (e) => consoleErrors.push(String(e)));

// Fake Google consent. Playwright can't intercept a redirected navigation, so
// intercept our connect endpoint, read its redirect to Google, and bounce
// straight back to the callback with the nonce as the (auto-approved) code.
await page.route("**/api/v1/storage/google-drive/connect**", async (route) => {
  const response = await route.fetch({ maxRedirects: 0 });
  const google = new URL(response.headers()["location"]);
  if (google.hostname !== "accounts.google.com") throw new Error("unexpected redirect " + google);
  if (
    google.searchParams.get("scope") !== "openid email https://www.googleapis.com/auth/drive.file"
  )
    throw new Error("wrong scope");
  await route.fulfill({
    status: 302,
    headers: {
      location: `${BASE}/api/v1/auth/google/callback?code=${google.searchParams.get("nonce")}&state=${google.searchParams.get("state")}`,
    },
  });
});

await page.goto(`${BASE}/login`);
await page.getByPlaceholder("you@example.com").fill(`e2e-${Date.now()}@example.com`);
await page.getByRole("button", { name: "Sign in", exact: true }).click();
await page.waitForURL(`${BASE}/`);
log("signed in");

await page.goto(`${BASE}/settings#storage`);
await page.getByRole("link", { name: "Connect" }).click();
await page.getByText("Google Drive connected").waitFor();
await page.getByText("Google account storage").waitFor();
log("Google Drive connected (fake consent), quota shown");

await page.goto(`${BASE}/files`);
await page.getByText("Your vault is empty").waitFor();
const input = page.locator('input[type="file"]');
await input.setInputFiles([
  {
    name: "Resume-2026.pdf",
    mimeType: "application/pdf",
    buffer: makePdf(["Sai Bykani - Resume", "Selenium, JMeter, TestNG", "Experience"]),
  },
  { name: "Certificate.png", mimeType: "image/png", buffer: makePng() },
  {
    name: "JMeter-notes.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# JMeter notes\n\n- Thread groups\n- <script>alert(1)</script> stays text\n",
    ),
  },
  {
    name: "malware.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("MZ\x90\x00 this is an exe"),
  },
]);
await page.getByText("upload failed").waitFor({ timeout: 20000 });
await page.getByText("doesn't match .pdf").waitFor();
log(
  "3 uploads succeeded, disguised executable rejected:",
  await page.getByText("doesn't match .pdf").innerText(),
);
await page.getByRole("link", { name: "Resume-2026.pdf" }).waitFor();
await page.screenshot({ path: `${out}/files-list.png` });

// Preview the PDF (pdf.js under our CSP), go to page 2.
await page.getByRole("link", { name: "Resume-2026.pdf" }).click();
await page.waitForURL(/\/files\/[0-9a-f-]+$/);
await page.getByText("of 3").waitFor({ timeout: 20000 });
await page.getByRole("button", { name: "Next page" }).click();
const canvasWidth = await page.locator("canvas").evaluate((c) => c.width);
if (canvasWidth < 100) throw new Error("PDF did not render");
log("PDF rendered with pdf.js, 3 pages, canvas width", canvasWidth);
await page.screenshot({ path: `${out}/files-preview-pdf.png` });

// Text preview stays text.
await page.goto(`${BASE}/files`);
await page.getByRole("link", { name: "JMeter-notes.md" }).click();
await page.locator("pre").getByText("<script>alert(1)</script> stays text").waitFor();
log("markdown previewed as inert text");

// New folder, move, rename, star, tag.
await page.goto(`${BASE}/files`);
await page.getByRole("button", { name: "New folder" }).click();
await page.getByRole("dialog").getByRole("textbox", { name: "Folder name" }).fill("Career");
await page.getByRole("button", { name: "Create", exact: true }).click();
await page.getByRole("button", { name: "Career", exact: true }).waitFor();
await page.getByRole("button", { name: "Actions for Resume-2026.pdf" }).click();
await page.getByRole("menuitem", { name: "Move", exact: true }).click();
await page.getByRole("dialog").getByRole("button", { name: "Career", exact: true }).click();
await page.getByRole("button", { name: "Move here" }).click();
await page.getByText("1 moved").waitFor();
await page.getByRole("button", { name: "Career", exact: true }).click();
await page.getByRole("navigation", { name: "Breadcrumb" }).getByText("Career").waitFor();
await page.getByRole("link", { name: "Resume-2026.pdf" }).waitFor();
log("folder created; file moved into Career; breadcrumbs update");

await page.getByRole("button", { name: "Actions for Resume-2026.pdf" }).click();
await page.getByRole("menuitem", { name: "Rename", exact: true }).click();
await page.getByRole("dialog").getByRole("textbox", { name: "Name" }).fill("Resume Sai");
await page.getByRole("button", { name: "Rename", exact: true }).click();
await page.getByRole("link", { name: "Resume Sai.pdf" }).waitFor();
log("renamed; extension preserved -> Resume Sai.pdf");

await page.getByRole("button", { name: "Actions for Resume Sai.pdf" }).click();
await page.getByRole("menuitem", { name: "Tags", exact: true }).click();
await page.getByLabel("Add a tag").fill("career");
await page.keyboard.press("Enter");
await page.getByLabel("Add a tag").fill("selenium");
await page.getByRole("button", { name: "Save tags" }).click();
await page.getByRole("button", { name: "Actions for Resume Sai.pdf" }).click();
await page.getByRole("menuitem", { name: "Star", exact: true }).click();
await page.getByLabel("Starred").first().waitFor();
log("tagged #career #selenium and starred");

// Collections.
await page.goto(`${BASE}/collections`);
await page.getByRole("button", { name: "Create", exact: true }).first().click();
await page.getByText("Created My Career").waitFor();
await page.goto(`${BASE}/files?view=starred`);
await page.getByRole("button", { name: "Actions for Resume Sai.pdf" }).click();
await page.getByRole("menuitem", { name: "Add to collection", exact: true }).click();
await page
  .getByRole("dialog")
  .getByRole("button", { name: /My Career/ })
  .click();
await page.getByText("Added to My Career").waitFor();
await page.goto(`${BASE}/collections`);
await page.getByText("1 file ·").waitFor();
log("collection created from template and file added");

// Trash, undo, trash again, delete forever.
await page.goto(`${BASE}/files`);
await page.getByRole("button", { name: "Actions for Certificate.png" }).click();
await page.getByRole("menuitem", { name: "Move to trash", exact: true }).click();
await page.getByRole("button", { name: "Undo" }).click();
await page.getByText("1 restored").waitFor();
await page.getByRole("link", { name: "Certificate.png" }).waitFor();
await page.getByRole("button", { name: "Actions for Certificate.png" }).click();
await page.getByRole("menuitem", { name: "Move to trash", exact: true }).click();
await page.goto(`${BASE}/files?view=trash`);
await page.getByRole("button", { name: "Actions for Certificate.png" }).click();
await page.getByRole("menuitem", { name: "Delete forever", exact: true }).click();
await page.getByRole("button", { name: "Delete forever", exact: true }).click();
await page.getByText("1 deleted permanently").waitFor();
await page.getByText("Trash is empty").waitFor();
log("trash -> undo -> trash -> delete forever (with confirmation)");

await page.goto(`${BASE}/`);
await page.getByText("Recent files").waitFor();
await page.getByRole("link", { name: /Resume Sai.pdf/ }).waitFor();
await page.screenshot({ path: `${out}/dashboard-live.png` });
log("dashboard shows live metrics and recent files");

const serious = consoleErrors.filter((e) => !e.includes("favicon"));
console.log("console errors:", serious.length ? serious : "none");
await browser.close();
console.log("FILES FLOW OK");
