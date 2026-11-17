import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test("device identity, diagnostics, confirmed sync and unchanged repeat", async ({
  page,
  request,
}) => {
  const key = `Sync fixture ${Date.now()}`;
  const folder = path.resolve(`../.runtime/e2e-sync-${Date.now()}`);
  await fs.mkdir(folder, { recursive: true });
  await fs.writeFile(
    path.join(folder, `${key}.gb`),
    Buffer.from((key + " synthetic legal test content").repeat(1000)),
  );
  const headers = { "X-RLM-Request": "1" };
  expect(
    (
      await request.put("/api/settings", {
        headers,
        data: {
          import_roots: [folder],
          export_root: folder,
        },
      })
    ).ok(),
  ).toBe(true);
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
    await request.post("/api/imports/scan", { headers, data: { root: folder } })
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
  await page.goto("/");
  await page.getByRole("button", { name: "Dispositivi", exact: true }).click();
  await page
    .getByRole("button", { name: "Aggiungi dispositivo", exact: true })
    .click();
  await page.getByLabel("Nome descrittivo", { exact: true }).fill(key);
  await page
    .getByLabel("Hostname o IP", { exact: true })
    .fill("test-pi.invalid");
  await page.getByLabel("Dispositivo predefinito", { exact: true }).check();
  await page
    .getByRole("button", { name: "Salva dispositivo", exact: true })
    .click();
  await page
    .getByRole("button", { name: "1. Verifica fingerprint", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Ho verificato questa fingerprint",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "3. Test SSH e diagnostica", exact: true })
    .click();
  await expect(page.getByText("Synthetic Pi", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "../.runtime/increment3-devices.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Sincronizzazione", exact: true })
    .click();
  await page.getByLabel("Cerca nella libreria", { exact: true }).fill(key);
  await page.getByRole("checkbox", { name: new RegExp(key) }).check();
  await page
    .getByRole("button", { name: "Analizza e prepara dry-run", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Conferma e sincronizza", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Conferma e sincronizza", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel(
      "Confermo di essere autorizzato a trasferire questi giochi sul mio Raspberry.",
    )
    .check();
  await page
    .getByRole("button", { name: "Conferma e sincronizza", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Report finale", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Analizza e prepara dry-run", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Conferma e sincronizza", exact: true }),
  ).toBeVisible();
  const runs = await (await request.get("/api/sync/runs")).json();
  expect(runs[0].plan.required_bytes).toBe(0);
  await page.screenshot({
    path: "../.runtime/increment3-sync.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../.runtime/increment3-sync-mobile.png",
    fullPage: true,
  });
});
