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
};

export type WorkpaperSummary = {
  id: number;
  control_id: string;
  run_id: number;
  sample_id: number | null;
  status: WorkpaperStatus;
  created_at: string;
  edited_at: string;
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
  }>;
  exceptions_by_severity: Record<Severity, number>;
  workpapers: WorkpaperSummary[];
};

export type DatasetCount = {
  dataset: string;
  rows: number;
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
