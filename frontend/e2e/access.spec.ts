import { test, expect, chromium, webkit } from "@playwright/test";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import path from "node:path";

const base = "http://127.0.0.1:18002";
const python =
  process.platform === "win32"
    ? "../.venv/Scripts/python.exe"
    : "../.venv/bin/python";

function archive(format: string, title: string, rom: Buffer) {
  if (format === "ZIP") return zip(`${title}.nes`, rom);
  return execFileSync(
    python,
    [
      "-c",
      `
import sys, json, base64, tempfile
from pathlib import Path
import py7zr
sys.path.insert(0, '../tests')
from rar_fixtures import rar
request = json.load(sys.stdin)
raw = base64.b64decode(request['data'])
with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / 'test'
    if request['format'] == '7z':
        with py7zr.SevenZipFile(target, 'w') as output:
            output.writestr(raw, request['name'])
    else:
        rar(target, {request['name']: raw}, version=4 if request['format'] == 'RAR4' else 5)
    sys.stdout.buffer.write(target.read_bytes())
`,
    ],
    {
      input: JSON.stringify({
        format,
        name: `${title}.nes`,
        data: rom.toString("base64"),
      }),
      windowsHide: true,
    },
  );
}
const password = randomBytes(24).toString("hex");
let server: ChildProcess;

function zip(name: string, data: Buffer) {
  const filename = Buffer.from(name);
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++)
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  crc = (crc ^ 0xffffffff) >>> 0;
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50);
  local.writeUInt16LE(20, 4);
  local.writeUInt32LE(crc, 14);
  local.writeUInt32LE(data.length, 18);
  local.writeUInt32LE(data.length, 22);
  local.writeUInt16LE(filename.length, 26);
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50);
  central.writeUInt16LE(20, 4);
  central.writeUInt16LE(20, 6);
  central.writeUInt32LE(crc, 16);
  central.writeUInt32LE(data.length, 20);
  central.writeUInt32LE(data.length, 24);
  central.writeUInt16LE(filename.length, 28);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50);
  end.writeUInt16LE(1, 8);
  end.writeUInt16LE(1, 10);
  end.writeUInt32LE(46 + filename.length, 12);
  end.writeUInt32LE(30 + filename.length + data.length, 16);
  return Buffer.concat([local, filename, data, central, filename, end]);
}

test.beforeAll(async () => {
  server = spawn(
    python,
    [
      "-m",
      "uvicorn",
      "e2e_app:app",
      "--app-dir",
      "../tests",
      "--host",
      "127.0.0.1",
      "--port",
      "18002",
    ],
    {
      windowsHide: true,
      stdio: "ignore",
      env: {
        ...process.env,
        RLM_DATA_DIR: path.resolve(
          `../.runtime/access-e2e-${randomBytes(8).toString("hex")}`,
        ),
      },
    },
  );
  for (let i = 0; i < 80; i++) {
    try {
      const response = await fetch(`${base}/api/health`);
      if (response.ok) return;
    } catch {
      /* booting */
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("Isolated auth server not ready");
});
test.afterAll(() => {
  if (server?.pid) {
    if (process.platform === "win32")
      execFileSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], {
        windowsHide: true,
        stdio: "ignore",
      });
    else server.kill("SIGTERM");
  }
});

for (const [name, engine] of [
  ["Chromium Android viewport", chromium],
  ["WebKit iPhone viewport", webkit],
] as const) {
  test(`authenticated mobile ZIP/RAR4/RAR5/7z upload, installation and logout: ${name}`, async () => {
    test.setTimeout(90000);
    const browser = await engine.launch();
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    // Simulate the missing secure-context API on plain HTTP LAN; SHA-256 must still work.
    await context.addInitScript(() =>
      Object.defineProperty(Crypto.prototype, "subtle", {
        get: () => undefined,
        configurable: true,
      }),
    );
    try {
      await page.goto(base);
      const status = await (
        await page.request.get(`${base}/api/access/status`)
      ).json();
      if (!status.configured) {
        await page.locator(".advanced-navigation > summary").click();
        await page
          .getByRole("button", { name: "Impostazioni", exact: true })
          .click();
        await page
          .getByLabel("Nuova password amministratore", { exact: true })
          .fill(password);
        await page
          .getByLabel("Ripeti password", { exact: true })
          .fill(password);
        await page
          .getByRole("button", { name: "Configura password", exact: true })
          .click();
        await expect(
          page.getByRole("button", {
            name: "Esci dalla sessione",
            exact: true,
          }),
        ).toBeVisible();
      } else {
        await page
          .getByLabel("Password amministratore", { exact: true })
          .fill(password);
        await page.getByRole("button", { name: "Accedi", exact: true }).click();
        await expect(
          page.getByRole("heading", { name: "Aggiungi giochi", exact: true }),
        ).toBeVisible();
      }
      const auth = await (
        await page.request.get(`${base}/api/access/status`)
      ).json();
      expect(auth.authenticated).toBeTruthy();
      const headers = { "X-RLM-Request": "1", "X-RLM-CSRF": auth.csrf };
      expect(
        (
          await page.request.post(`${base}/api/devices`, {
            headers,
            data: {
              name: "Mobile test Pi",
              host: "test-pi.invalid",
              is_default: true,
            },
          })
        ).ok(),
      ).toBeTruthy();
      const formats = ["ZIP", "RAR4", "RAR5", "7z"];
      const titles = formats.map(
        (format) => `Mobile ${name.split(" ")[0]} ${format} ${Date.now()}`,
      );
      const files = formats.map((format, index) => {
        const rom = Buffer.concat([
          Buffer.from([78, 69, 83, 26, 1, 0, ...Array(10).fill(0)]),
          Buffer.alloc(16384, 41),
        ]);
        rom.write(titles[index], 16);
        const extension = format.startsWith("RAR")
          ? "rar"
          : format.toLowerCase();
        return {
          name: `${titles[index]}.${extension}`,
          mimeType: "application/octet-stream",
          buffer: archive(format, titles[index], rom),
        };
      });
      await page
        .getByRole("button", { name: "Aggiungi giochi", exact: true })
        .click();
      await page
        .getByLabel("File giochi", { exact: true })
        .setInputFiles(files);
      await page
        .getByRole("button", { name: "Analizza selezione", exact: true })
        .click();
      for (const title of titles)
        await expect(
          page.getByRole("heading", { name: title, exact: true }),
        ).toBeVisible({ timeout: 30000 });
      await page
        .getByLabel("Confermo di poter utilizzare questi file.", {
          exact: false,
        })
        .check();
      await page
        .getByRole("button", { name: "Installa automaticamente", exact: true })
        .click();
      await expect(page.getByText("Installato", { exact: true })).toHaveCount(
        4,
        { timeout: 45000 },
      );
      for (const section of [
        "Dashboard",
        "La mia libreria",
        "Grandi Classici",
        "Da Recuperare",
        "Installazioni",
        "Impostazioni",
      ]) {
        if (
          !(await page
            .getByRole("button", { name: section, exact: true })
            .isVisible())
        ) {
          await page.locator(".advanced-navigation > summary").click();
        }
        await page.getByRole("button", { name: section, exact: true }).click();
        await expect(
          page.getByRole("heading", { name: section, exact: true }).first(),
        ).toBeVisible();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBeTruthy();
      }
      await page
        .getByRole("button", { name: "Esci dalla sessione", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Accedi", exact: true }),
      ).toBeVisible();
      expect((await page.request.get(`${base}/api/settings`)).status()).toBe(
        401,
      );
    } finally {
      await context.close();
      await browser.close();
    }
  });
}

test("connection failure can be retried without exposing the app", async ({
  page,
}) => {
  await page.route("**/api/access/status", (route) => route.abort());
  await page.goto(base);
  await expect(
    page.getByText("Il PC ospite non risponde.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Installa automaticamente", exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/api/access/status");
  await page
    .getByRole("button", { name: "Riprova connessione", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Accedi", exact: true }),
  ).toBeVisible();
});

test("expired session during upload returns to login", async ({ page }) => {
  await page.goto(base);
  await page
    .getByLabel("Password amministratore", { exact: true })
    .fill(password);
  await page.getByRole("button", { name: "Accedi", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Aggiungi giochi", exact: true }),
  ).toBeVisible();
  const auth = await (
    await page.request.get(`${base}/api/access/status`)
  ).json();
  await page.route("**/api/installations/*/uploads/*", async (route) => {
    await page.request.post(`${base}/api/access/logout`, {
      headers: { "X-RLM-Request": "1", "X-RLM-CSRF": auth.csrf },
    });
    await route.continue();
  });
  await page
    .getByLabel("File giochi", { exact: true })
    .setInputFiles({
      name: "Expired.nes",
      mimeType: "application/octet-stream",
      buffer: Buffer.concat([
        Buffer.from([78, 69, 83, 26, 1, 0, ...Array(10).fill(0)]),
        Buffer.alloc(16384, 41),
      ]),
    });
  await page
    .getByRole("button", { name: "Analizza selezione", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Accedi", exact: true }),
  ).toBeVisible();
  expect((await page.request.get(`${base}/api/games`)).status()).toBe(401);
});
