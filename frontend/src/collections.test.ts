import { describe, expect, it } from "vitest";
import { chooseCandidate } from "./Collections";

const candidates = [
  {
    id: "cover",
    game_id: 1,
    title: "One",
    kind: "cover",
    recommended: true,
    match_basis: "hash",
    asset: { license: "CC0-1.0", source_url: "https://example.org" },
  },
  {
    id: "shot-a",
    game_id: 1,
    title: "One",
    kind: "screenshot",
    recommended: true,
    match_basis: "hash",
    asset: { license: "CC0-1.0", source_url: "https://example.org" },
  },
  {
    id: "shot-b",
    game_id: 1,
    title: "One",
    kind: "screenshot",
    recommended: false,
    match_basis: "hash",
    asset: { license: "CC0-1.0", source_url: "https://example.org" },
  },
  {
    id: "other",
    game_id: 2,
    title: "Two",
    kind: "screenshot",
    recommended: true,
    match_basis: "hash",
    asset: { license: "CC0-1.0", source_url: "https://example.org" },
  },
];
describe("media association preview", () => {
  it("selects one screenshot without removing a cover or another game's image", () => {
    expect(
      chooseCandidate(
        ["cover", "shot-a", "other"],
        candidates[2],
        candidates,
        true,
      ),
    ).toEqual(["cover", "other", "shot-b"]);
  });
  it("allows rejecting an image without selecting an alternative automatically", () => {
    expect(
      chooseCandidate(["cover", "shot-a"], candidates[1], candidates, false),
    ).toEqual(["cover"]);
  });
});
