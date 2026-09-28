import { useEffect, useState } from "react";
import { ApiError, getCompleteness, getDataSource, getDatasets, setDataSource, uploadDataset } from "../api";
import { CompletenessTable, Message, notifySourceChange } from "../components";
import { Link } from "../router";
import type { Completeness, DataSource, DatasetCount } from "../types";

const TABLES: Array<{ id: string; label: string; note: string }> = [
  {
    id: "hr_roster",
    label: "HR roster",
    note: "Employees, including termination dates. Load this table before the others.",
  },
  {
    id: "role_permissions",
    label: "Role permissions",
    note: "Permission granted by each application role.",
  },
  {
    id: "sod_conflict_rules",
    label: "Segregation-of-duties rules",
    note: "Permission pairs one person must not hold together.",
  },
  {
    id: "iam_accounts",
    label: "IAM accounts",
    note: "Application accounts, status, and last login.",
  },
  {
    id: "change_tickets",
    label: "Change tickets",
    note: "Requested, approved, and deployed changes.",
  },
];

export function DataPage() {
  const [counts, setCounts] = useState<DatasetCount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [uploading, setUploading] = useState<string | null>(null);
  const [source, setSource] = useState<DataSource | null>(null);
  const [coverage, setCoverage] = useState<Completeness[] | null>(null);

  useEffect(() => {
    document.title = "Data · The ITAudit System";
  }, []);

  useEffect(() => {
    let cancelled = false;
    getDatasets()
      .then((rows) => {
        if (!cancelled) {
          setCounts(rows);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(messageFrom(caught));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getDataSource(), getCompleteness()])
      .then(([nextSource, nextCoverage]) => {
        if (!cancelled) {
          setSource(nextSource);
          setCoverage(nextCoverage.controls);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(messageFrom(caught));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [counts]);

  async function chooseSource(dataset: DataSource["dataset"]) {
    setError(null);
    try {
      const next = await setDataSource(dataset);
      setSource(next);
      notifySourceChange();
      setCounts(await getDatasets());
    } catch (caught) {
      setError(messageFrom(caught));
    }
  }

  async function upload(dataset: string) {
    const file = files[dataset];
    if (!file) {
      setError("Choose a CSV before uploading.");
      return;
    }
    setUploading(dataset);
    setError(null);
    setNotice(null);
    try {
      const csv = await file.text();
      const result = await uploadDataset(dataset, csv);
      setCounts(await getDatasets());
      setNotice(`Loaded ${result.rows} rows into ${labelFor(result.dataset)}.`);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setUploading(null);
    }
  }

  if (!counts && !error) {
    return <Message tone="loading">Loading table counts.</Message>;
  }

  const byName = new Map((counts ?? []).map((row) => [row.dataset, row.rows]));

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Data</h1>
          <p className="lede">Upload a CSV to replace one table. The row count is what is stored now.</p>
        </div>
      </div>
      {source ? (
        <section className="panel">
          <h2>Data source</h2>
          <div className="source-switch">
            <button type="button" aria-pressed={source.dataset === "demo"} onClick={() => void chooseSource("demo")}>
              Demo data
            </button>
            {source.allow_real_data ? (
              <button
                type="button"
                aria-pressed={source.dataset === "company"}
                onClick={() => void chooseSource("company")}
              >
                Company data
              </button>
            ) : null}
            {source.allow_real_data ? <Link to="/import">Import company data</Link> : null}
          </div>
          <p className="meta">Controls, samples, and workpapers record the source that was active when they were created.</p>
        </section>
      ) : null}
      {coverage ? (
        <section className="panel">
          <h2>Completeness</h2>
          <p className="meta">Records loaded in the active source, how many each control tests, and why the rest are excluded.</p>
          <CompletenessTable rows={coverage} />
        </section>
      ) : null}
      {error ? <Message tone="error">{error}</Message> : null}
      {notice ? <Message tone="note">{notice}</Message> : null}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Table</th>
              <th>Rows</th>
              <th>CSV</th>
            </tr>
          </thead>
          <tbody>
            {TABLES.map((table) => (
              <tr key={table.id}>
                <td>
                  <strong>{table.label}</strong>
                  <span className="cell-note">{table.note}</span>
                </td>
                <td>{byName.get(table.id) ?? 0}</td>
                <td>
                  <form
                    className="upload-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void upload(table.id);
                    }}
                  >
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      aria-label={`CSV for ${table.label}`}
                      onChange={(event) => {
                        const file = event.target.files?.[0] ?? null;
                        setFiles((current) => ({ ...current, [table.id]: file }));
                      }}
                    />
                    <button type="submit" disabled={uploading !== null}>
                      {uploading === table.id ? "Uploading" : "Upload"}
                    </button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function labelFor(dataset: string): string {
  return TABLES.find((table) => table.id === dataset)?.label ?? dataset;
}

function messageFrom(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "The data page could not reach the API.";
}
