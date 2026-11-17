import { afterEach, describe, expect, it, vi } from "vitest";
import { api, bytes, waitForJob } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});
describe("local API client", () => {
  it("sends the local mutation header and body", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) });
    vi.stubGlobal("fetch", fetcher);
    expect(await api("/settings", "PUT", { import_roots: [] })).toEqual({
      id: 1,
    });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/settings",
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({ "X-RLM-Request": "1" }),
        body: '{"import_roots":[]}',
      }),
    );
  });
  it("surfaces server validation failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Percorso non valido" }),
      }),
    );
    await expect(api("/settings")).rejects.toThrow("Percorso non valido");
  });
  it("surfaces failed jobs instead of claiming completion", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "failed", error: "Hash errato" }),
      }),
    );
    await expect(waitForJob("test", vi.fn())).rejects.toThrow("Hash errato");
  });
  it("formats storage amounts including zero", () => {
    expect(bytes(0)).toBe("0 B");
    expect(bytes(1024)).toBe("1 KiB");
    expect(bytes(1024 ** 3)).toBe("1 GiB");
  });
});
