import { useState } from "react";
import { ApiError, commitImport, inspectImport, validateImport } from "../api";
import { CompletenessTable, Message, notifySourceChange } from "../components";
import type { ImportField, ImportResult, ValidationReport } from "../types";

const FILES = [
  { id: "hr_roster", label: "HR roster" },
  { id: "iam_accounts", label: "IAM accounts" },
  { id: "role_permissions", label: "Role permissions" },
  { id: "change_tickets", label: "Change tickets" },
] as const;

const STEPS = ["Upload files", "Column mapping", "Value normalization", "Validation report"];

type Mapping = Record<string, string>;

export function ImportWizard() {
  const [step, setStep] = useState(0);
  const [csv, setCsv] = useState<Record<string, string>>({});
  const [fileNames, setFileNames] = useState<Record<string, string>>({});
  const [headers, setHeaders] = useState<Record<string, string[]>>({});
  const [fields, setFields] = useState<Record<string, ImportField[]>>({});
  const [mappings, setMappings] = useState<Record<string, Mapping>>({});
  const [statusValues, setStatusValues] = useState<string[]>([]);
  const [statusMap, setStatusMap] = useState<Record<string, string>>({});
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [imported, setImported] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const ready = FILES.every((file) => Boolean(csv[file.id]));

  async function toMapping() {
    setBusy(true);
    setError(null);
    try {
      const inspections = await Promise.all(FILES.map((file) => inspectImport(file.id, csv[file.id])));
      const nextHeaders: Record<string, string[]> = {};
      const nextFields: Record<string, ImportField[]> = {};
      const nextMappings: Record<string, Mapping> = {};
      for (const inspection of inspections) {
        nextHeaders[inspection.dataset] = inspection.headers;
        nextFields[inspection.dataset] = inspection.fields;
        nextMappings[inspection.dataset] = inspection.mapping;
      }
      const accounts = inspections.find((item) => item.dataset === "iam_accounts");
      setHeaders(nextHeaders);
      setFields(nextFields);
      setMappings(nextMappings);
      setStatusValues(accounts?.status_values ?? []);
      setStatusMap(accounts?.status_map ?? {});
      setStep(1);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toNormalization() {
    setBusy(true);
    setError(null);
    try {
      const accounts = await inspectImport("iam_accounts", csv.iam_accounts, mappings.iam_accounts);
      setStatusValues(accounts.status_values);
      setStatusMap((current) => {
        const next: Record<string, string> = {};
        for (const value of accounts.status_values) {
          next[value] = current[value] ?? accounts.status_map[value] ?? "";
        }
        return next;
      });
      setStep(2);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toReport() {
    setBusy(true);
    setError(null);
    try {
      setReport(await validateImport(bundle()));
      setImported(null);
      setStep(3);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    setBusy(true);
    setError(null);
    try {
      const result = await commitImport(bundle());
      setImported(result);
      setReport(result.validation);
      notifySourceChange();
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(false);
    }
  }

  function bundle() {
    const files: Record<string, { csv: string; mapping: Mapping; status_map: Record<string, string> }> = {};
    for (const file of FILES) {
      files[file.id] = {
        csv: csv[file.id],
        mapping: mappings[file.id] ?? {},
        status_map: file.id === "iam_accounts" ? statusMap : {},
      };
    }
    return files;
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Import company data</h1>
          <p className="lede">Map the four files onto the control tables, then review the validation report before import.</p>
        </div>
      </div>
      <ol className="wizard-steps">
        {STEPS.map((label, index) => (
          <li key={label} className={index === step ? "current" : undefined} aria-current={index === step ? "step" : undefined}>
            {index + 1}. {label}
          </li>
        ))}
      </ol>
      {error ? <Message tone="error">{error}</Message> : null}
      {step === 0 ? (
        <section className="panel">
          <h2>Upload files</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>File</th>
                  <th>Template</th>
                </tr>
              </thead>
              <tbody>
                {FILES.map((file) => (
                  <tr key={file.id}>
                    <td>{file.label}</td>
                    <td>
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        aria-label={`${file.label} file`}
                        onChange={(event) => {
                          const chosen = event.target.files?.[0];
                          if (!chosen) {
                            return;
                          }
                          void chosen.text().then((text) => {
                            setCsv((current) => ({ ...current, [file.id]: text }));
                            setFileNames((current) => ({ ...current, [file.id]: chosen.name }));
                          });
                        }}
                      />
                      {fileNames[file.id] ? <span className="cell-note">{fileNames[file.id]}</span> : null}
                    </td>
                    <td>
                      <a href={`/api/import/templates/${file.id}`}>Download template</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="button-row">
            <button type="button" className="primary" disabled={!ready || busy} onClick={() => void toMapping()}>
              {busy ? "Reading files" : "Continue"}
            </button>
          </div>
        </section>
      ) : null}
      {step === 1 ? (
        <section className="panel">
          <h2>Column mapping</h2>
          <p className="meta">Suggested matches come from the column names. A required field must be mapped before import.</p>
          {FILES.map((file) => (
            <div key={file.id} className="mapping-block">
              <h3>{file.label}</h3>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Required field</th>
                      <th>File column</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(fields[file.id] ?? []).map((field) => (
                      <tr key={field.field}>
                        <td>
                          {labelFor(field.field)}
                          {field.required ? "" : " (optional)"}
                        </td>
                        <td>
                          <select
                            aria-label={`Column for ${labelFor(field.field)} on ${file.label}`}
                            value={mappings[file.id]?.[field.field] ?? ""}
                            onChange={(event) => {
                              const header = event.target.value;
                              setMappings((current) => ({
                                ...current,
                                [file.id]: { ...current[file.id], [field.field]: header },
                              }));
                            }}
                          >
                            <option value="">Not mapped</option>
                            {(headers[file.id] ?? []).map((header) => (
                              <option key={header} value={header}>
                                {header}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          <div className="button-row">
            <button type="button" onClick={() => setStep(0)}>
              Back
            </button>
            <button type="button" className="primary" disabled={busy} onClick={() => void toNormalization()}>
              {busy ? "Reading values" : "Continue"}
            </button>
          </div>
        </section>
      ) : null}
      {step === 2 ? (
        <section className="panel">
          <h2>Value normalization</h2>
          <p className="meta">
            Dates such as 2026-01-15, 01/15/2026, and 15-Jan-2026 are accepted. Map each account status value to active or
            disabled. An unmapped status is skipped.
          </p>
          {statusValues.length === 0 ? (
            <p className="meta">No account status values were found. Map the status column if the file has one.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Value in the file</th>
                    <th>Stored status</th>
                  </tr>
                </thead>
                <tbody>
                  {statusValues.map((value) => (
                    <tr key={value}>
                      <td>{value}</td>
                      <td>
                        <select
                          aria-label={`Status for ${value}`}
                          value={statusMap[value] ?? ""}
                          onChange={(event) => setStatusMap((current) => ({ ...current, [value]: event.target.value }))}
                        >
                          <option value="">Unmapped</option>
                          <option value="active">active</option>
                          <option value="disabled">disabled</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="button-row">
            <button type="button" onClick={() => setStep(1)}>
              Back
            </button>
            <button type="button" className="primary" disabled={busy} onClick={() => void toReport()}>
              {busy ? "Validating" : "Continue"}
            </button>
          </div>
        </section>
      ) : null}
      {step === 3 && report ? (
        <section className="panel">
          <h2>Validation report</h2>
          {report.can_import ? (
            <p className="meta">Required fields are mapped. Rows below will be loaded. Skipped rows stay out of the tables.</p>
          ) : (
            <Message tone="error">Import is blocked. Map every required field.</Message>
          )}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Rows in file</th>
                  <th>Rows loaded</th>
                  <th>Rows skipped</th>
                </tr>
              </thead>
              <tbody>
                {report.datasets.map((dataset) => (
                  <tr key={dataset.dataset}>
                    <td>{dataset.label}</td>
                    <td>{dataset.rows_seen}</td>
                    <td>{dataset.rows_loaded}</td>
                    <td>{dataset.rows_skipped}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.datasets.map((dataset) =>
            dataset.skipped.length === 0 ? null : (
              <div key={`${dataset.dataset}-skips`}>
                <h3>{dataset.label} skips</h3>
                <ul className="skip-list">
                  {dataset.skipped.map((skip) => (
                    <li key={`${dataset.dataset}-${skip.line}-${skip.reason}`}>
                      Line {skip.line}: {skip.reason}
                    </li>
                  ))}
                </ul>
              </div>
            ),
          )}
          {imported ? (
            <>
              <Message tone="note">Company data is now the active source.</Message>
              <h3>Completeness</h3>
              <CompletenessTable rows={imported.completeness} />
            </>
          ) : null}
          <div className="button-row">
            <button type="button" onClick={() => setStep(2)} disabled={busy}>
              Back
            </button>
            <button type="button" className="primary" disabled={!report.can_import || busy || imported !== null} onClick={() => void commit()}>
              {busy ? "Importing" : "Import company data"}
            </button>
          </div>
        </section>
      ) : null}
    </>
  );
}

function labelFor(field: string): string {
  return field.replaceAll("_", " ");
}

function messageFrom(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "The import could not be completed.";
}
