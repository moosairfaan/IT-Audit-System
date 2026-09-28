export type Severity = "high" | "medium" | "low";

export type WorkpaperStatus = "draft" | "reviewed" | "approved";

export type ExceptionRow = {
  exception_id: string;
  severity?: Severity;
} & Record<string, string | number | boolean | null | undefined>;

export type Control = {
  control_id: string;
  name: string;
  objective: string;
  risk_addressed: string;
  population: string;
  suggested_action: string;
};

export type TestRun = {
  run_id: number;
  control_id: string;
  name: string;
  objective: string;
  risk_addressed: string;
  population: string;
  population_count: number;
  exception_count: number;
  exceptions: ExceptionRow[];
  run_at: string;
  dataset: "demo" | "company";
  dataset_label: string;
  completeness: Completeness;
};

export type Sample = {
  sample_id: number;
  control_id: string;
  run_id: number;
  method: "random" | "risk_based";
  seed: number;
  population_size: number;
  sample_size: number;
  selected_ids: string[];
  created_at: string;
  dataset?: "demo" | "company";
  dataset_label?: string;
};

export type WorkpaperSummary = {
  id: number;
  control_id: string;
  run_id: number;
  sample_id: number | null;
  status: WorkpaperStatus;
  created_at: string;
  edited_at: string;
  dataset?: "demo" | "company";
  dataset_label?: string;
};

export type Workpaper = WorkpaperSummary & {
  sections: Record<string, string>;
  markdown: string;
  reviewer_notes: string | null;
};

export type Overview = {
  controls_tested: number;
  control_count: number;
  total_exceptions: number;
  workpapers_by_status: Record<WorkpaperStatus, number>;
  exceptions_by_control: Array<{
    control_id: string;
    name: string;
    exception_count: number;
    run_id: number | null;
    dataset: "demo" | "company" | null;
    dataset_label: string | null;
  }>;
  exceptions_by_severity: Record<Severity, number>;
  workpapers: WorkpaperSummary[];
};

export type DatasetCount = {
  dataset: string;
  rows: number;
};

export type DataSource = {
  dataset: "demo" | "company";
  label: string;
  allow_real_data: boolean;
};

export type Exclusion = {
  reason: string;
  count: number;
};

export type Completeness = {
  records_loaded: number;
  records_tested: number;
  records_excluded: number;
  exclusions: Exclusion[];
  control_id?: string;
  name?: string;
};

export type SodPair = {
  permission_a: string;
  permission_b: string;
  description: string;
};

export type AuditRules = {
  dormant_days: number;
  privileged_roles: string[];
  critical_systems: string[];
  sod_pairs: SodPair[];
  allow_real_data?: boolean;
};

export type ImportField = {
  field: string;
  header: string;
  required: boolean;
  mapped: boolean;
};

export type ImportInspection = {
  dataset: string;
  label: string;
  headers: string[];
  fields: ImportField[];
  mapping: Record<string, string>;
  status_values: string[];
  status_map: Record<string, string>;
};

export type ValidationDataset = {
  dataset: string;
  label: string;
  rows_seen: number;
  rows_loaded: number;
  rows_skipped: number;
  rows_flagged: number;
  skipped: Array<{ line: number; reason: string }>;
  flagged: Array<{ line: number; reason: string }>;
  coverage: ImportField[];
  blocked: boolean;
};

export type ValidationReport = {
  datasets: ValidationDataset[];
  can_import: boolean;
};

export type ImportResult = {
  dataset: string;
  label: string;
  validation: ValidationReport;
  completeness: Completeness[];
};

export const SECTION_FIELDS: Array<[string, string]> = [
  ["control_objective", "Control objective"],
  ["risk_addressed", "Risk addressed"],
  ["procedure_performed", "Procedure performed"],
  ["population_and_sample", "Population and sample"],
  ["results", "Results"],
  ["exceptions_noted", "Exceptions noted"],
  ["conclusion", "Conclusion"],
];
