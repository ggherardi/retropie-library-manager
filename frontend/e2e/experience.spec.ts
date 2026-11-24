import { expect, test } from "@playwright/test";

test("recognizes a Commodore tape and explains the installation block", async ({
  page,
  request,
}) => {
  await request.post("/api/devices", {
    headers: { "X-RLM-Request": "1" },
    data: { name: "Tape Pi", host: "test-pi.invalid", is_default: true },
  });
  await page.goto("/");
  await page.getByLabel("File giochi", { exact: true }).setInputFiles({
    name: "Arkanoid.tap",
    mimeType: "application/octet-stream",
    buffer: Buffer.concat([
      Buffer.from("C64-TAPE-RAW"),
      Buffer.from([1, 0, 0, 0, 1, 0, 0, 0, 42]),
    ]),
  });
  await page
    .getByRole("button", { name: "Analizza selezione", exact: true })
    .click();
  const card = page.locator(".install-card").filter({
    has: page.getByRole("heading", { name: "Arkanoid", exact: true }),
  });
  await expect(
    card.getByText("Console non supportata", { exact: true }),
  ).toBeVisible();
  await expect(card.getByText("Commodore 64", { exact: true })).toBeVisible();
  await card.locator(":scope > summary").click();
  await expect(
    card.getByText(
      "L’importazione sul Raspberry non dispone di un profilo per i nastri Commodore 64.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    card.getByRole("button", { name: "Risolvi problema" }),
  ).toHaveCount(0);
});

test("compact cards, contextual actions, tabs, live updates and refresh persistence", async ({
  page,
  request,
}) => {
  const headers = { "X-RLM-Request": "1" };
  await request.post("/api/devices", {
    headers,
    data: { name: "Experience Pi", host: "test-pi.invalid", is_default: true },
  });
  const title = `Compact ${Date.now()}`;
  const rom = Buffer.concat([
    Buffer.from([78, 69, 83, 26, 1, 0, ...Array(10).fill(0)]),
    Buffer.alloc(16384, 63),
  ]);
  rom.write(title, 16);
  const counts = new Map<string, number>();
  page.on("request", (request) => {
    if (
      request.method() === "GET" &&
      request.url().includes("/api/installations")
    ) {
      const key = new URL(request.url()).pathname;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  });
  await page.goto("/");
  await page.getByLabel("File giochi", { exact: true }).setInputFiles([
    { name: `${title}.nes`, mimeType: "application/octet-stream", buffer: rom },
    {
      name: "Broken.iso",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("invalid disc image"),
    },
  ]);
  await page
    .getByRole("button", { name: "Analizza selezione", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  const card = page
    .locator(".install-card")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) });
  await expect(card).not.toHaveAttribute("open", "");
  expect((await card.boundingBox())!.height).toBeLessThan(125);
  await expect(page.getByLabel("Avanzamento installazioni")).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Sezioni installazioni" });
  const tabBoxes = await tabs
    .getByRole("button")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().top),
    );
  expect(Math.max(...tabBoxes) - Math.min(...tabBoxes)).toBeLessThan(5);

  await card.locator(":scope > summary").focus();
  await page.keyboard.press("Enter");
  await expect(card).toHaveAttribute("open", "");
  await expect(card.locator(".path").first()).toBeVisible();
  await card.locator(":scope > summary").click();
  await page
    .getByLabel("Confermo di poter utilizzare questi file.", { exact: false })
    .check();
  await page
    .getByRole("button", { name: "Installa automaticamente", exact: true })
    .click();
  await expect(card.getByText("Installato", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  const bid = await page.evaluate(() =>
    sessionStorage.getItem("rlm-installation-batch"),
  );
  await page
    .getByRole("navigation", { name: "Sezioni installazioni" })
    .getByRole("button", { name: "In corso", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("navigation", { name: "Sezioni installazioni" })
    .getByRole("button", { name: "Completati", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await card.locator(":scope > summary").click();
  await expect(
    card.getByRole("button", { name: "Apri nella libreria" }),
  ).toBeVisible();
  await expect(
    card.getByRole("button", { name: "Riprova", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("rlm-installation-batch")),
  ).toBe(bid);
  await page
    .getByRole("navigation", { name: "Sezioni installazioni" })
    .getByRole("button", { name: "Serve intervento", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toHaveCount(0);
  expect([...counts.values()].every((n) => n < 30)).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
