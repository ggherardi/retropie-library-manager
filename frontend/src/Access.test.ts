import { describe, it, expect, vi } from "vitest";
import { requestHeaders, requestId, setCSRF, sha256Hex } from "./api";

describe("LAN-compatible browser requests", () => {
  it("hashes upload bytes without a secure-context SubtleCrypto API", async () => {
    vi.stubGlobal("crypto", {
      getRandomValues: globalThis.crypto.getRandomValues.bind(
        globalThis.crypto,
      ),
    });
    try {
      expect(await sha256Hex(new TextEncoder().encode("abc").buffer)).toBe(
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("generates request IDs without randomUUID", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: globalThis.crypto.getRandomValues.bind(
        globalThis.crypto,
      ),
    });
    try {
      expect(requestId()).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("propagates CSRF to API and upload headers and clears it on logout", () => {
    setCSRF("synthetic-csrf");
    expect(requestHeaders()["X-RLM-CSRF"]).toBe("synthetic-csrf");
    setCSRF("");
    expect(requestHeaders()["X-RLM-CSRF"]).toBeUndefined();
  });
});
