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
