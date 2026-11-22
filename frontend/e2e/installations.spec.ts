import { expect, test } from "@playwright/test";

test("browser selection to verified installation, independent ambiguity and repeat", async ({
  page,
  request,
}) => {
  const headers = { "X-RLM-Request": "1" };
  const response = await request.post("/api/devices", {
    headers,
    data: {
      name: "Installation test Pi",
      host: "test-pi.invalid",
      is_default: true,
    },
  });
  expect(response.ok()).toBeTruthy();
  const title = `Pipeline ${Date.now()}`;
  const rom = Buffer.concat([
    Buffer.from([78, 69, 83, 26, 1, 0, ...Array(10).fill(0)]),
    Buffer.alloc(16384, 42),
  ]);
  rom.write(title, 16, "utf8");
  const beforeCount = (await (await request.get("/api/stats")).json()).games;
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Aggiungi giochi", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Modalità installazione")).toHaveValue(
    "install",
  );
  await page.getByLabel("File giochi", { exact: true }).setInputFiles([
    { name: `${title}.nes`, mimeType: "application/octet-stream", buffer: rom },
    {
      name: "README.md",
      mimeType: "text/plain",
      buffer: Buffer.from("A document"),
    },
    {
      name: "Unknown.bin",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("unidentified raw data"),
    },
  ]);
  await page
    .getByRole("button", { name: "Analizza selezione", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Anteprima pronta", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("1 giochi pronti.", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Confermo di poter utilizzare questi file.", { exact: false })
    .check();
  await page
    .getByRole("button", { name: "Installa automaticamente", exact: true })
    .click();
  await expect(page.getByText("Installato", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page
    .locator(".install-card")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) })
    .locator(":scope > summary")
    .click();
  await expect(
    page
      .locator(".install-card[open]")
      .getByText("Avvio: non verificato", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Serve il tuo intervento", { exact: true }).last(),
  ).toBeVisible();
  expect((await (await request.get("/api/stats")).json()).games).toBe(
    beforeCount + 1,
  );
  await page
    .locator(".install-card")
    .filter({
      has: page.getByRole("heading", { name: "Unknown", exact: true }),
    })
    .locator(":scope > summary")
    .click();
  await page.getByRole("button", { name: "Salta questo elemento" }).click();
  await page
    .getByRole("button", { name: "Nuova selezione", exact: true })
    .click();
  await page.getByLabel("File giochi", { exact: true }).setInputFiles({
    name: `${title}.nes`,
    mimeType: "application/octet-stream",
    buffer: rom,
  });
  await page
    .getByRole("button", { name: "Analizza selezione", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Confermo di poter utilizzare questi file.", { exact: false })
    .check();
  await page
    .getByRole("button", { name: "Installa automaticamente", exact: true })
    .click();
  await expect(page.getByText("Già installato", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  const batches = await (await request.get("/api/installations")).json();
  const current = await (
    await request.get(`/api/installations/${batches.batches[0].id}`)
  ).json();
  expect(current.items[0].progress.report.transferred_bytes).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
