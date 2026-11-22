import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { Progress } from "./Installations";
import { describe, expect, it } from "vitest";
import { selectedFiles, statusLabel } from "./Installations";

describe("installation browser selection", () => {
  it("keeps multiple files and does not fabricate Windows paths", () => {
    const files = [
      new File(["cue"], "Game.cue"),
      new File(["bin"], "Game.bin"),
    ];
    expect(selectedFiles(files, true).map((p) => p.relative)).toEqual([
      "Game.cue",
      "Game.bin",
    ]);
  });
  it("preserves relative companion paths and respects optional recursion", () => {
    const root = new File(["root"], "Top.nes");
    const child = new File(["child"], "Game.cue");
    Object.defineProperty(root, "webkitRelativePath", {
      value: "Selection/Top.nes",
    });
    Object.defineProperty(child, "webkitRelativePath", {
      value: "Selection/discs/Game.cue",
    });
    expect(selectedFiles([root, child], true).map((p) => p.relative)).toEqual([
      "Top.nes",
      "discs/Game.cue",
    ]);
    expect(selectedFiles([root, child], false)).toHaveLength(1);
  });
  it("does not label transfers as played or visible", () => {
    expect(statusLabel.installed).toBe("File installati e verificati");
    expect(statusLabel.pending_refresh).toContain("metadati in attesa");
    expect(Object.values(statusLabel).join(" ")).not.toMatch(
      /giocabile|avviato con successo/i,
    );
  });
});

describe("honest accessible progress", () => {
  it("does not assign a percentage to an unknown phase", () => {
    const html = renderToStaticMarkup(
      createElement(Progress, {
        progress: { kind: "indeterminate" },
        label: "Verifica dei file",
      }),
    );
    expect(html).toContain('aria-label="Verifica dei file"');
    expect(html).not.toContain("value=");
  });
  it("uses measured bytes and a label when supplied", () => {
    const html = renderToStaticMarkup(
      createElement(Progress, {
        progress: { kind: "bytes", value: 30, total: 100 },
        label: "Copia",
      }),
    );
    expect(html).toContain('value="30"');
    expect(html).toContain('max="100"');
  });
  it("does not draw a transfer bar for a completed state", () => {
    expect(
      renderToStaticMarkup(
        createElement(Progress, {
          progress: { kind: "none" },
          label: "Completato",
        }),
      ),
    ).toBe("");
  });
});
