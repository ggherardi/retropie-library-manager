import { expect, test } from "@playwright/test";
import crypto from "node:crypto";

function manifest(key: string, count: number) {
  return {
    id: key,
    name: `Fonte ${key}`,
    entries: Array.from({ length: count }, (_, index) => {
      const filename = `${key}-${index}.gb`;
      const content = Buffer.from(`fixture-${filename}`.repeat(8192));
      return {
        id: `game-${index}`,
        title: `${key} titolo ${index}`,
        platform: "gb",
        filename,
        url: `https://fixtures.example/${filename}`,
        size: content.length,
        sha256: crypto.createHash("sha256").update(content).digest("hex"),
        license: "CC0-1.0",
        rights_url: "https://fixtures.example/rights",
        distribution: "homebrew",
        redistribution_allowed: true,
      };
    }),
  };
}

test("filtered selection, explicit confirmation, concurrent queue, pause and resume", async ({
  page,
  request,
}) => {
  const key = `manual-${Date.now()}`;
  const source = manifest(key, 2);
  expect(
    (
      await request.put(`/api/providers/${key}`, {
        headers: { "X-RLM-Request": "1" },
        data: source,
      })
    ).ok(),
  ).toBe(true);
  const before = (await (await request.get("/api/downloads")).json()).total;
  await page.goto("/");
  await page.getByText("Avanzate", { exact: true }).click();
  await page
    .getByRole("button", { name: "Game Discovery", exact: true })
    .click();
  await page.getByLabel("Cerca giochi", { exact: true }).fill(key);
  await expect(page.getByText("2 risultati", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Seleziona tutti i risultati filtrati" })
    .click();
  await page.getByRole("button", { name: "Prepara riepilogo" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect((await (await request.get("/api/downloads")).json()).total).toBe(
    before,
  );
  await page
    .getByRole("button", { name: "Conferma e avvia 2 download" })
    .click();
  await expect(
    page
      .getByRole("heading", { name: "Download Manager", exact: true })
      .first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Pausa", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("In pausa", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Riprendi", exact: true })
    .first()
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/games?q=${key}`)).json()).total,
      { timeout: 20000 },
    )
    .toBe(2);
  await page.screenshot({
    path: "../.runtime/increment2-download-manager.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Game Discovery", exact: true })
    .click();
  await page.getByLabel("Cerca giochi", { exact: true }).fill(key);
  await expect(
    page.getByText("Importato", { exact: true }).first(),
  ).toBeVisible();
  const imported = (await (await request.get(`/api/games?q=${key}`)).json())
    .items[0];
  expect(
    (
      await request.put(`/api/games/${imported.id}`, {
        headers: { "X-RLM-Request": "1" },
        data: {
          title: "Manual correction",
          genre: "Personal genre",
          license: "Da verificare",
        },
      })
    ).ok(),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Anteprima arricchimento", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Applica metadati e copertine autorizzate",
      exact: true,
    }),
  ).toBeEnabled();
  await page
    .getByRole("button", {
      name: "Applica metadati e copertine autorizzate",
      exact: true,
    })
    .click();
  await expect(
    page.getByText(
      "Arricchimento completato. I campi già compilati sono stati conservati.",
    ),
  ).toBeVisible();
  const enriched = await (
    await request.get(`/api/games/${imported.id}`)
  ).json();
  expect(enriched.license).toBe("CC0-1.0");
  expect(enriched.title).toBe("Manual correction");
  expect(enriched.genre).toBe("Personal genre");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../.runtime/increment2-discovery-mobile.png",
    fullPage: true,
  });
});

test("automatic rules remain reviewable and require confirmation", async ({
  page,
  request,
}) => {
  const key = `auto-${Date.now()}`;
  const source = manifest(key, 1);
  await request.put(`/api/providers/${key}`, {
    headers: { "X-RLM-Request": "1" },
    data: source,
  });
  const before = (await (await request.get("/api/downloads")).json()).total;
  await page.goto("/");
  await page.getByText("Avanzate", { exact: true }).click();
  await page
    .getByRole("button", { name: "Game Discovery", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Selezione automatica", exact: true })
    .click();
  await page
    .getByText("Capacità RetroPie e regole automatiche", { exact: true })
    .click();
  await page.getByLabel("Capacità nominale microSD · GB").fill("128");
  await page.getByLabel("Download simultanei").fill("3");
  await page
    .getByRole("group", { name: "Piattaforme automatiche" })
    .getByLabel("Game Boy", { exact: true })
    .check();
  await page
    .getByRole("group", { name: "Fonti automatiche autorizzate" })
    .getByLabel(`Fonte ${key}`, { exact: true })
    .check();
  await page
    .getByLabel("Licenze ammesse · selezione multipla")
    .selectOption("CC0-1.0");
  await page.getByRole("button", { name: "Prepara riepilogo" }).click();
  await expect(
    page.getByRole("button", { name: "Conferma e avvia 1 download" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect((await (await request.get("/api/downloads")).json()).total).toBe(
    before,
  );
  await page.getByRole("button", { name: "Prepara riepilogo" }).click();
  await page
    .getByRole("button", { name: "Conferma e avvia 1 download" })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/games?q=${key}`)).json()).total,
      { timeout: 20000 },
    )
    .toBe(1);
});
