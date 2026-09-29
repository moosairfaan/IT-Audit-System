import type {
  AuditRules,
  Completeness,
  Control,
  DataSource,
  DatasetCount,
  ImportInspection,
  ImportResult,
  Overview,
  Sample,
  TestRun,
  ValidationReport,
  Workpaper,
  WorkpaperStatus,
  WorkpaperSummary,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  const base = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
  return `${base}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(apiUrl(path), { ...init, headers });
  if (!response.ok) {
    throw new ApiError(await readDetail(response), response.status);
  }
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("text/markdown") || type.startsWith("text/plain")) {
    return (await response.text()) as T;
  }
  return (await response.json()) as T;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail) {
      return body.detail;
    }
  } catch {
    return `Request failed (${response.status})`;
  }
  return `Request failed (${response.status})`;
}

export function getOverview(): Promise<Overview> {
  return request<Overview>("/api/overview");
}

export function getControls(): Promise<Control[]> {
  return request<{ controls: Control[] }>("/api/controls").then((body) => body.controls);
}

export function getRuns(): Promise<TestRun[]> {
  return request<{ runs: TestRun[] }>("/api/tests").then((body) => body.runs);
}

export function runTest(controlId: string): Promise<TestRun> {
  return request<TestRun>(`/api/tests/${encodeURIComponent(controlId)}/run`, { method: "POST" });
}

export function runAllTests(): Promise<TestRun[]> {
  return request<{ runs: TestRun[] }>("/api/tests/run-all", { method: "POST" }).then((body) => body.runs);
}

export function createSample(
  controlId: string,
  method: Sample["method"],
  sampleSize: number,
  seed: number | null,
): Promise<Sample> {
  return request<Sample>(`/api/tests/${encodeURIComponent(controlId)}/sample`, {
    method: "POST",
    body: JSON.stringify({
      method,
      sample_size: sampleSize,
      seed,
    }),
  });
}

export function getLatestSample(controlId: string): Promise<Sample> {
  return request<Sample>(`/api/tests/${encodeURIComponent(controlId)}/sample`);
}

export function generateWorkpaper(controlId: string, runId: number, sampleId: number | null): Promise<Workpaper> {
  return request<Workpaper>("/api/workpapers/generate", {
    method: "POST",
    body: JSON.stringify({
      control_id: controlId,
      run_id: runId,
      sample_id: sampleId,
    }),
  });
}

export function getWorkpaper(id: number): Promise<Workpaper> {
  return request<Workpaper>(`/api/workpapers/${id}`);
}

export function listWorkpapers(): Promise<WorkpaperSummary[]> {
  return request<{ workpapers: WorkpaperSummary[] }>("/api/workpapers").then((body) => body.workpapers);
}

export function updateWorkpaper(
  id: number,
  patch: { sections?: Record<string, string>; status?: WorkpaperStatus },
): Promise<Workpaper> {
  return request<Workpaper>(`/api/workpapers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function exportWorkpaper(id: number): Promise<string> {
  return request<string>(`/api/workpapers/${id}/export`);
}

export function getDatasets(): Promise<DatasetCount[]> {
  return request<{ datasets: DatasetCount[] }>("/api/datasets").then((body) => body.datasets);
}

export function uploadDataset(dataset: string, csv: string): Promise<{ dataset: string; rows: number }> {
  return request(`/api/upload/${encodeURIComponent(dataset)}`, {
    method: "POST",
    body: csv,
    headers: { "Content-Type": "text/csv" },
  });
}

export function getDataSource(): Promise<DataSource> {
  return request<DataSource>("/api/data-source");
}

export function setDataSource(dataset: DataSource["dataset"]): Promise<DataSource> {
  return request<DataSource>("/api/data-source", {
    method: "POST",
    body: JSON.stringify({ dataset }),
  });
}

export function getRules(): Promise<AuditRules> {
  return request<AuditRules>("/api/settings");
}

export function saveRules(rules: AuditRules): Promise<AuditRules> {
  return request<AuditRules>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(rules),
  });
}

export function getCompleteness(): Promise<{ dataset: string; label: string; controls: Completeness[] }> {
  return request("/api/completeness");
}

export function inspectImport(
  dataset: string,
  csv: string,
  mapping?: Record<string, string>,
): Promise<ImportInspection> {
  return request<ImportInspection>("/api/import/inspect", {
    method: "POST",
    body: JSON.stringify({ dataset, csv, mapping: mapping ?? null }),
  });
}

export function validateImport(
  files: Record<string, { csv: string; mapping: Record<string, string>; status_map: Record<string, string> }>,
): Promise<ValidationReport> {
  return request<ValidationReport>("/api/import/validate", {
    method: "POST",
    body: JSON.stringify({ files }),
  });
}

export function commitImport(
  files: Record<string, { csv: string; mapping: Record<string, string>; status_map: Record<string, string> }>,
): Promise<ImportResult> {
  return request<ImportResult>("/api/import/commit", {
    method: "POST",
    body: JSON.stringify({ files }),
  });
}
