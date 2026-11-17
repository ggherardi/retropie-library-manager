export type Game = {
  id: number;
  title: string;
  author?: string;
  publisher?: string;
  platform: string;
  region: string;
  year: number | null;
  genre: string;
  description: string;
  cover_path: string;
  size: number;
  format: string;
  local_path: string;
  sha256: string;
  favorite: boolean;
  provenance: string;
  license: string;
  files: { path: string; relative: string; sha256: string; size: number }[];
};
export type Candidate = Game & { duplicate: boolean };
export type ScanResult = {
  candidates: Candidate[];
  warnings: string[];
  scanned_files: number;
};
export type ExportResult = {
  target_capacity?: { usable_bytes: number; selection_fits_target: boolean };
  required_bytes: number;
  free_bytes: number;
  destination?: string;
  dry_run: boolean;
  manifest: unknown;
};
export type Job<T = unknown> = {
  id: string;
  kind: string;
  status: string;
  error: string;
  result: T;
};
export type Settings = {
  import_roots: string[];
  export_root: string;
  data_dir?: string;
};
export type Provider = {
  id: string;
  name: string;
  entries: {
    id: string;
    title: string;
    platform: string;
    license: string;
    size: number;
    rights_url: string;
  }[];
};

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-RLM-Request": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Servizio non disponibile" }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Controlla i campi inseriti e i percorsi.",
    );
  }
  return response.json() as Promise<T>;
}

export function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const unit = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4);
  return `${(value / 1024 ** unit).toLocaleString("it-IT", { maximumFractionDigits: 1 })} ${["B", "KiB", "MiB", "GiB", "TiB"][unit]}`;
}

export async function waitForJob<T>(
  id: string,
  onStatus: (
    status: string,
    progress?: { scanned_files?: number; total_files?: number },
  ) => void,
): Promise<Job<T>> {
  for (;;) {
    const job = await api<Job<T>>(`/jobs/${id}`);
    onStatus(
      job.status,
      (
        job.result as {
          progress?: { scanned_files?: number; total_files?: number };
        }
      )?.progress,
    );
    if (["failed", "cancelled"].includes(job.status))
      throw new Error(job.error);
    if (job.status === "completed") return job;
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
}
