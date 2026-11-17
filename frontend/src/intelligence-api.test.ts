import { describe, it, expect } from "vitest";
import { stateLabel, count } from "./intelligence-api";

describe("intelligence evidence labels", () => {
  it("distinguishes hash validation from operator hardware tests", () => {
    expect(stateLabel("complete")).toContain("hash");
    expect(stateLabel("complete")).not.toContain("Test riuscito");
    expect(stateLabel("passed")).toContain("operatore");
    expect(stateLabel("untested")).toBe("Mai testato");
  });
  it("shows explicit missing states and readable catalog counts", () => {
    expect(stateLabel("incomplete")).toContain("Dipendenze");
    expect(stateLabel("unvalidated")).toBe("Non validato");
    expect(count(10000)).toBe("10.000");
  });
});
