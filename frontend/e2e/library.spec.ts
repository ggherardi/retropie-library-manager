import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

test("import, edit, favorites, list, dry-run and export through the UI", async ({
  page,
}) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "rlm-e2e-"));
  const source = path.join(root, "source");
  const destination = path.join(root, "exports");
  await fs.mkdir(source);
  await fs.mkdir(destination);
  const title = `Test ${Date.now()}`;
  await fs.writeFile(
    path.join(source, `${title}.nes`),
    `synthetic fixture ${title}`,
  );
  await page.goto("/");
  await page.getByText("Avanzate", { exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Aggiungi giochi", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Impostazioni", exact: true }).click();
  await page.getByLabel("Sorgenti autorizzate").fill(source);
  await page
    .getByLabel("Cartella di destinazione delle esportazioni")
    .fill(destination);
  await page.getByRole("button", { name: "Salva impostazioni" }).click();
  await expect(page.getByText("Impostazioni salvate.")).toBeVisible();
  await page.getByRole("button", { name: "Importazione", exact: true }).click();
  await page.getByLabel("Cartella da scansionare").fill(source);
  await page.getByRole("button", { name: "Avvia scansione" }).click();
  await expect(
    page.getByRole("heading", { name: "Anteprima importazione" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Importa 1 giochi", exact: true })
    .click();
  await expect(
    page.getByText("1 giochi importati, 0 duplicati saltati."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Catalogo", exact: true }).click();
  await page.getByLabel("Cerca nella libreria").fill(title);
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: `Preferito ${title}`, exact: true })
    .click();
  await page.getByRole("button", { name: "Vista lista" }).click();
  await page.getByRole("heading", { name: title, exact: true }).click();
  await page.getByLabel("Genere", { exact: true }).fill("Puzzle");
  await page.getByRole("button", { name: "Salva modifiche" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: /^Preferiti/ }).click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page.getByLabel(`Seleziona ${title}`, { exact: true }).check();
  await page.getByRole("button", { name: "Esportazione", exact: true }).click();
  await page.getByRole("button", { name: "Calcola spazio · dry-run" }).click();
  await expect(
    page.getByText("Integrità verificata.", { exact: false }),
  ).toBeVisible();
  expect(await fs.readdir(destination)).toHaveLength(0);
  await page.getByRole("button", { name: "Copia la selezione" }).click();
  await expect(
    page.getByText("Esportazione completata e verificata."),
  ).toBeVisible();
  expect((await fs.readdir(destination)).length).toBe(1);
  await page.screenshot({ path: "../.runtime/ui-export.png", fullPage: true });
  await page
    .getByRole("button", { name: "Aggiungi giochi", exact: true })
    .click();
  await page.screenshot({
    path: "../.runtime/ui-dashboard.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Aggiungi giochi", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../.runtime/ui-mobile.png", fullPage: true });
  await fs.rm(root, { recursive: true, force: true });
});
