import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test("classics remain separate from installed games, manual collection and media quality", async ({
  page,
  request,
}) => {
  const title = `Collection fixture ${Date.now()}`;
  const root = path.resolve(`../.runtime/e2e-collections-${Date.now()}`);
  await fs.mkdir(root, { recursive: true });
  await fs.writeFile(
    path.join(root, `${title}.gb`),
    Buffer.from(title.repeat(40)),
  );
  const headers = { "X-RLM-Request": "1" };
  await request.put("/api/settings", {
    headers,
    data: { import_roots: [root], export_root: root },
  });
  const scan = await (
    await request.post("/api/imports/scan", { headers, data: { root } })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/jobs/${scan.id}`)).json()).status,
    )
    .toBe("completed");
  const preview = await (await request.get(`/api/jobs/${scan.id}`)).json();
  const imported = await (
    await request.post(`/api/imports/${scan.id}/commit`, {
      headers,
      data: {
        candidate_ids: preview.result.candidates.map(
          (c: { id: number }) => c.id,
        ),
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/jobs/${imported.id}`)).json()).status,
    )
    .toBe("completed");
  await page.goto("/");
  await page
    .getByRole("button", { name: "Da Recuperare", exact: true })
    .click();
  await page.getByLabel("Cerca nelle collezioni").fill("Super Mario Bros.");
  await expect(
    page.getByText("Da recuperare · non installato").first(),
  ).toBeVisible();
  await expect(
    page.getByText("Super Mario Bros.", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Collezione Completa", exact: true })
    .click();
  await page.getByLabel("Cerca nelle collezioni").fill(title);
  await page.getByRole("button", { name: title, exact: true }).click();
  const detail = page.getByRole("dialog", {
    name: "Dettaglio gioco collezione",
  });
  await expect(detail.getByText("Descrizione sconosciuta")).toBeVisible();
  await expect(detail.getByText("Screenshot mancante")).toBeVisible();
  await detail
    .getByRole("button", { name: "Aggiungi ai Grandi Classici", exact: true })
    .click();
  await expect(detail).not.toBeVisible();
  await page
    .getByRole("button", { name: "Grandi Classici", exact: true })
    .click();
  await page.getByLabel("Cerca nelle collezioni").fill(title);
  await page.getByRole("button", { name: title, exact: true }).click();
  await page
    .getByRole("button", { name: "Rimuovi dai Grandi Classici", exact: true })
    .click();
  await expect(
    page.getByText("La raccolta aspetta i tuoi classici"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Collezione Completa", exact: true })
    .click();
  await page.getByLabel("Cerca nelle collezioni").fill(title);
  await expect(
    page.getByRole("button", { name: title, exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Qualità e media", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Trova media autorizzati" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});
