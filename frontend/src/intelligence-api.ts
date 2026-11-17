import { api } from "./api";

export const intel = <T>(path: string, method = "GET", body?: unknown) =>
  api<T>("/intelligence" + path, method, body);
export const count = (value = 0) => value.toLocaleString("it-IT");
export const stateLabel = (value: string) =>
  ({
    complete: "Completo · hash verificati",
    incomplete: "Dipendenze / hash da risolvere",
    unvalidated: "Non validato",
    stale: "Da rivalidare · DAT o file cambiato",
    passed: "Test riuscito · operatore",
    failed: "Non riuscito",
    untested: "Mai testato",
    queued: "In coda",
    running: "In elaborazione",
    cancelling: "Annullamento in corso",
    cancelled: "Annullato",
    completed: "Completato",
  })[value] || value;
export function saveReport(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export type Source = {
  id: string;
  name: string;
  count?: number;
  sha256: string;
  config: {
    core: string;
    version: string;
    source_url: string;
    revision: string;
  };
};
export type Summary = {
  catalog_records: number;
  catalog_games: number;
  unique_families: number;
  family_scope: string;
  clones: number;
  bios_records: number;
  local_files: number;
  present_files: number;
  missing_files: number;
  authorized_downloads: number;
  validated_games: number;
  tested_games: number;
  platforms: { id: string; name: string; catalog: number; local: number }[];
};
export type Entry = {
  uid: string;
  name: string;
  title: string;
  platform: string;
  system: string;
  manufacturer: string;
  year: string;
  genre: string;
  players: number;
  orientation: string;
  controls: string;
  parent: string;
  romof: string;
  family: string;
  kind: string;
  owned_game_ids: number[];
  source_id: string;
};
export type EntryDetail = Entry & {
  source: Source;
  variants: Pick<Entry, "uid" | "name" | "title">[];
  preferred_uid: string | null;
  components: { name: string; size: number; crc: string; sha1: string }[];
  details: { dependencies?: string[]; declared_status?: string };
  download_authorized: false;
};
export type Run = {
  id: string;
  kind: string;
  status: string;
  progress: {
    phase?: string;
    records?: number;
    done?: number;
    total?: number;
    bytes?: number;
    total_bytes?: number;
  };
  result: Record<string, unknown>;
  error: string;
  created_at: string;
};
export type Audit = {
  checked_at: string;
  cores: Record<
    string,
    {
      installed: boolean;
      version: string | null;
      sha256: string | null;
      error?: string;
    }
  >;
  configs: Record<string, string>;
  installed_cores: string[];
  bios_inventory: { path: string; size: number }[];
  emulationstation_sessions: {
    pid: number;
    tty_nr: number;
    valid_local_session: boolean;
  }[];
  space: { free: number; total: number };
};
export type Device = {
  id: string;
  config: { name: string; host: string };
  diagnostics: { arcade?: Audit };
};
export type Insight = {
  preferred_core: string;
  machine_mode: string;
  test_status: string;
  screenshot_path: string;
  catalog_uid: string;
  test_evidence: { device_id?: string; note?: string; sha256?: string };
};
export type Validation = {
  status: string;
  source_sha: string;
  mode: string;
  report: {
    problems: { set: string; file: string; reason: string }[];
    core: string;
    source_version: string;
    compatibility: string;
    launch_note: string;
    bios: string[];
    checks: unknown[];
  };
};
