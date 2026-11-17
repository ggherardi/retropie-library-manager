import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

test("massive catalog UI, parent/clone preference, archive validation, reports and mobile", async ({
  page,
  request,
}) => {
  const root = path.resolve(`../.runtime/e2e-intelligence-${Date.now()}`);
  await fs.mkdir(root, { recursive: true });
  const suffix = String(Date.now());
  const name = `demo${suffix}`;
  const payload = `synthetic arcade fixture ${suffix}`;
  const zip = path.join(root, `${name}.zip`);
  const python =
    process.platform === "win32"
      ? "../.venv/Scripts/python.exe"
      : "../.venv/bin/python";
  execFileSync(python, [
    "-c",
    'import zipfile,sys; z=zipfile.ZipFile(sys.argv[1],"w"); z.writestr("program.bin",sys.argv[2]); z.close()',
    zip,
    payload,
  ]);
  const rows = [
    {
      name,
      title: `Intelligence fixture ${suffix}`,
      system: "CPS-1",
      players: 2,
      components: [
        {
          name: "program.bin",
          size: Buffer.byteLength(payload),
          sha1: createHash("sha1").update(payload).digest("hex"),
        },
      ],
    },
    ...Array.from({ length: 79 }, (_, i) => ({
      name: `${name}clone${i}`,
      title: `Intelligence variant ${suffix} ${i}`,
      parent: name,
      system: "CPS-1",
    })),
  ];
  const manifest = path.join(root, "catalog.json");
  await fs.writeFile(manifest, JSON.stringify(rows));
  const headers = { "X-RLM-Request": "1" };
  expect(
    (
      await request.put("/api/settings", {
        headers,
        data: { import_roots: [root], export_root: root },
      })
    ).ok(),
  ).toBe(true);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Cataloghi DAT", exact: true })
    .click();
  await page.getByLabel("ID catalogo", { exact: true }).fill(name);
  await page
    .getByLabel("Nome catalogo", { exact: true })
    .fill(`Synthetic ${suffix}`);
  await page.getByLabel("Percorso del manifest").fill(manifest);
  await page.getByLabel("Core del DAT").selectOption("lr-mame2003");
  await page.getByLabel("Versione del ROM set").fill("0.78");
  await page
    .getByRole("button", { name: "Avvia importazione catalogo" })
    .click();
  await expect(page.getByText(`Synthetic ${suffix} · 80`)).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("tab", { name: "Esplora metadati" }).click();
  await page
    .getByRole("combobox", { name: "Catalogo DAT", exact: true })
    .selectOption(name);
  await expect(
    page.getByRole("heading", { name: "80 record", exact: true }),
  ).toBeVisible();
  expect(await page.locator(".intel-entry").count()).toBe(36);
  await page.getByRole("button", { name: "Successiva", exact: true }).click();
  await expect(page.getByText("2 / 3", { exact: true })).toBeVisible();
  await page.getByLabel("Solo parent").check();
  await expect(
    page.getByRole("heading", { name: "1 record", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: new RegExp(`Intelligence fixture ${suffix}`) })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText("Solo metadati · nessun download ROM"),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Scegli versione" }).first().click();
  await expect(
    dialog.getByRole("button", { name: "Preferita", exact: true }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "Chiudi dettaglio" }).click();
  async function job(id: string) {
    await expect
      .poll(
        async () =>
          (await (await request.get(`/api/jobs/${id}`)).json()).status,
      )
      .toBe("completed");
    return (await (await request.get(`/api/jobs/${id}`)).json()).result;
  }
  const scan = await (
    await request.post("/api/imports/scan", {
      headers,
      data: { root, platform: "arcade" },
    })
  ).json();
  const preview = await job(scan.id);
  const commit = await (
    await request.post(`/api/imports/${scan.id}/commit`, {
      headers,
      data: {
        candidate_ids: preview.candidates.map((c: { id: number }) => c.id),
        license: "CC0-1.0",
        provenance: "Synthetic browser fixture",
      },
    })
  ).json();
  await job(commit.id);
  await page.getByRole("tab", { name: "File e raccolte" }).click();
  await page.getByLabel("Cerca nei cataloghi massivi").fill(name);
  await page.getByLabel(`Seleziona ${name}`, { exact: true }).check();
  await page.getByLabel("DAT per la validazione").selectOption(name);
  await page
    .getByRole("button", { name: "Valida archivi selezionati" })
    .click();
  await expect(
    page.getByText("Completo · hash verificati", { exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await page.locator(".entry-main").first().click();
  await expect(
    page
      .getByRole("dialog")
      .locator(".intel-badges")
      .getByText("Mai testato", { exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Scarica report di validazione" })
    .click();
  expect((await download).suggestedFilename()).toMatch(/^validation-/);
  await page.getByRole("button", { name: "Chiudi dettaglio" }).click();
  await page.screenshot({
    path: "../.runtime/increment4-collections.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Neo Geo", exact: true }).click();
  await expect(
    page.getByText("Neo Geo · MVS / AES", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../.runtime/increment4-neogeo-mobile.png",
    fullPage: true,
  });
});
