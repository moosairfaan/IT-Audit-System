import { useMemo, useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "./router";
import type { ExceptionRow, Overview } from "./types";

const COLUMN_ORDER = [
  "exception_id",
  "severity",
  "employee_id",
  "name",
  "department",
  "system",
  "role",
  "termination_date",
  "last_login",
  "days_after_termination",
  "conflicting_pairs",
  "requested_by",
  "approved_by",
  "deployed_by",
  "approved_at",
  "deployed_at",
  "description",
  "reason",
];

const SEVERITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <p className="eyebrow">Financial services IT audit</p>
            <Link to="/" markCurrent={false}>
              The ITAudit System
            </Link>
          </div>
          <nav aria-label="Primary">
            <Link to="/">Overview</Link>
            <Link to="/data">Data</Link>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

export function Message({ tone, children }: { tone: "loading" | "error" | "note"; children: ReactNode }) {
  return (
    <p className={`message message-${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </p>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}

export function ExceptionTable({ rows }: { rows: ExceptionRow[] }) {
  const columns = useMemo(() => columnsFor(rows), [rows]);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("exception_id");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? rows.filter((row) => columns.some((column) => cellText(row[column]).toLowerCase().includes(needle)))
      : rows;
    return [...filtered].sort((left, right) => compareCells(left[sortKey], right[sortKey], sortKey, direction));
  }, [columns, direction, query, rows, sortKey]);

  function toggleSort(column: string) {
    if (sortKey === column) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(column);
    setDirection("asc");
  }

  return (
    <div className="table-block">
      <label className="filter">
        Filter exceptions
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Identifier, system, role" />
      </label>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} aria-sort={sortKey === column ? (direction === "asc" ? "ascending" : "descending") : "none"}>
                  <button type="button" onClick={() => toggleSort(column)}>
                    {heading(column)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length, 1)}>No exceptions match this filter.</td>
              </tr>
            ) : (
              visible.map((row) => (
                <tr key={row.exception_id}>
                  {columns.map((column) => (
                    <td key={column}>{column === "severity" ? <SeverityText value={row.severity} /> : cellText(row[column])}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <p className="meta">
        Showing {visible.length} of {rows.length}
      </p>
    </div>
  );
}

export function OverviewCharts({ overview }: { overview: Overview }) {
  const byControl = overview.exceptions_by_control;
  const controlMax = Math.max(...byControl.map((row) => row.exception_count), 1);
  const severityRows = [
    { severity: "High", exceptions: overview.exceptions_by_severity.high, fill: "#1b4f72" },
    { severity: "Medium", exceptions: overview.exceptions_by_severity.medium, fill: "#5d7f99" },
    { severity: "Low", exceptions: overview.exceptions_by_severity.low, fill: "#b7c5d1" },
  ];
  const severityMax = Math.max(...severityRows.map((row) => row.exceptions), 1);

  return (
    <div className="chart-grid">
      <section className="panel">
        <h2>Exceptions by control</h2>
        <div className="chart">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={byControl} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#e4e8ee" vertical={false} />
              <XAxis dataKey="control_id" tick={{ fill: "#5c6773", fontSize: 12 }} axisLine={{ stroke: "#d5dbe3" }} tickLine={false} />
              <YAxis allowDecimals={false} domain={[0, controlMax]} tick={{ fill: "#5c6773", fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "#eef2f5" }} />
              <Bar dataKey="exception_count" name="Exceptions" fill="#1b4f72" maxBarSize={42} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="panel">
        <h2>Exceptions by severity</h2>
        <div className="chart">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={severityRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#e4e8ee" vertical={false} />
              <XAxis dataKey="severity" tick={{ fill: "#5c6773", fontSize: 12 }} axisLine={{ stroke: "#d5dbe3" }} tickLine={false} />
              <YAxis allowDecimals={false} domain={[0, severityMax]} tick={{ fill: "#5c6773", fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "#eef2f5" }} />
              <Bar dataKey="exceptions" name="Exceptions" maxBarSize={42}>
                {severityRows.map((row) => (
                  <Cell key={row.severity} fill={row.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="meta">
          High is a terminated employee who still has access, or a segregation-of-duties conflict on payments or the general
          ledger. Medium is every other exception. Low is a dormant account or a shared account.
        </p>
      </section>
    </div>
  );
}

function SeverityText({ value }: { value: ExceptionRow["severity"] }) {
  if (!value) {
    return null;
  }
  return <span className={`severity severity-${value}`}>{value}</span>;
}

function columnsFor(rows: ExceptionRow[]): string[] {
  const present = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      present.add(key);
    }
  }
  const ordered = COLUMN_ORDER.filter((key) => present.has(key));
  const rest = [...present].filter((key) => !ordered.includes(key)).sort();
  return [...ordered, ...rest];
}

function heading(key: string): string {
  return key.replaceAll("_", " ");
}

function cellText(value: ExceptionRow[string]): string {
  if (value === null || value === undefined || value === "") {
    return "None";
  }
  return String(value);
}

function compareCells(
  left: ExceptionRow[string],
  right: ExceptionRow[string],
  key: string,
  direction: "asc" | "desc",
): number {
  const factor = direction === "asc" ? 1 : -1;
  if (key === "severity") {
    return ((SEVERITY_RANK[String(left)] ?? 9) - (SEVERITY_RANK[String(right)] ?? 9)) * factor;
  }
  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * factor;
  }
  return cellText(left).localeCompare(cellText(right), undefined, { numeric: true }) * factor;
}
