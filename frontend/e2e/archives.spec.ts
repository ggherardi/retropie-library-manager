import { expect, test } from "@playwright/test";

function zip(files: { name: string; data: Buffer }[]) {
  const chunks: Buffer[] = [];
  const directory: Buffer[] = [];
  let offset = 0;
  for (const file of files) {
    const name = Buffer.from(file.name);
    let crc = 0xffffffff;
    for (const byte of file.data) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++)
        crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
    crc = (crc ^ 0xffffffff) >>> 0;
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(file.data.length, 18);
    local.writeUInt32LE(file.data.length, 22);
    local.writeUInt16LE(name.length, 26);
    chunks.push(local, name, file.data);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(file.data.length, 20);
    central.writeUInt32LE(file.data.length, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE(offset, 42);
    directory.push(central, name);
    offset += local.length + name.length + file.data.length;
  }
  const central = Buffer.concat(directory);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...chunks, central, end]);
}

function crc32(data: Buffer) {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++)
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function rar4(files: { name: string; data: Buffer }[]) {
  const header = (body: Buffer) => {
    const crc = Buffer.alloc(2);
    crc.writeUInt16LE(crc32(body) & 65535);
    return Buffer.concat([crc, body]);
  };
  const main = Buffer.alloc(11);
  main[0] = 0x73;
  main.writeUInt16LE(13, 3);
  const parts = [Buffer.from([82, 97, 114, 33, 26, 7, 0]), header(main)];
  for (const file of files) {
    const name = Buffer.from(file.name);
    const body = Buffer.alloc(30 + name.length);
    body[0] = 0x74;
    body.writeUInt16LE(0x8000, 1);
    body.writeUInt16LE(32 + name.length, 3);
    body.writeUInt32LE(file.data.length, 5);
    body.writeUInt32LE(file.data.length, 9);
    body[13] = 2;
    body.writeUInt32LE(crc32(file.data), 14);
    body[22] = 20;
    body[23] = 0x30;
    body.writeUInt16LE(name.length, 24);
    body.writeUInt32LE(0x20, 26);
    name.copy(body, 30);
    parts.push(header(body), file.data);
  }
  const end = Buffer.alloc(5);
  end[0] = 0x7b;
  end.writeUInt16LE(7, 3);
  parts.push(header(end));
  return Buffer.concat(parts);
}

for (const format of ["zip", "rar"]) {
  test(`drop ${format}, automatic preparation and install without manual extraction`, async ({
    page,
    request,
  }) => {
    const headers = { "X-RLM-Request": "1" };
    expect(
      (
        await request.post("/api/devices", {
          headers,
          data: {
            name: "Archive test Pi",
            host: "test-pi.invalid",
            is_default: true,
          },
        })
      ).ok(),
    ).toBeTruthy();
    const title = `Archive ${format} ${Date.now()}`;
    const rom = Buffer.concat([
      Buffer.from([78, 69, 83, 26, 1, 0, ...Array(10).fill(0)]),
      Buffer.alloc(16384, 42),
    ]);
    rom.write(title, 16);
    const archive = (format === "rar" ? rar4 : zip)([
      { name: `${title}.nes`, data: rom },
      { name: "README.md", data: Buffer.from("documentation") },
    ]);
    await page.goto("/");
    const transfer = await page.evaluateHandle(
      ({ payload, format }) => {
        const dt = new DataTransfer();
        const data = Uint8Array.from(atob(payload), (character) =>
          character.charCodeAt(0),
        );
        dt.items.add(
          new File([data], `Games.${format}`, {
            type: "application/octet-stream",
          }),
        );
        return dt;
      },
      { payload: archive.toString("base64"), format },
    );
    await page
      .locator(".install-drop")
      .dispatchEvent("drop", { dataTransfer: transfer });
    await page
      .getByRole("button", { name: "Analizza selezione", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await page.locator(".install-card > summary").first().click();
    await page
      .getByText("Mostra dettagli archivio", { exact: false })
      .first()
      .click();
    await expect(
      page
        .getByText("File preparati automaticamente; originale conservato", {
          exact: true,
        })
        .first(),
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
    const batches = await (await request.get("/api/installations")).json();
    const current = await (
      await request.get(`/api/installations/${batches.batches[0].id}`)
    ).json();
    expect(current.counts.installed).toBe(1);
    expect(current.counts.prepared).toBe(1);
    expect(
      current.items.find(
        (item: { status: string }) => item.status === "installed",
      ).launched,
    ).toBe(false);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  });
}
