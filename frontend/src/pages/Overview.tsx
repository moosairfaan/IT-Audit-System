import { useEffect, useState } from "react";
import { ApiError, getOverview, runAllTests } from "../api";
import { Message, OverviewCharts, StatusBadge } from "../components";
import { Link } from "../router";
import type { Overview as OverviewData } from "../types";

export function Overview() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    document.title = "Overview · The ITAudit System";
  }, []);

  useEffect(() => {
    let cancelled = false;
    getOverview()
      .then((body) => {
        if (!cancelled) {
          setOverview(body);
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

  async function runAll() {
    setRunning(true);
    setError(null);
    try {
      await runAllTests();
      setOverview(await getOverview());
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setRunning(false);
    }
  }

  if (!overview && !error) {
    return <Message tone="loading">Loading the latest test runs.</Message>;
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Overview</h1>
          <p className="lede">Latest results for the five IT general controls.</p>
        </div>
        <button type="button" className="primary" onClick={() => void runAll()} disabled={running}>
          {running ? "Running all five tests" : "Run all five tests"}
        </button>
      </div>
      {error ? <Message tone="error">{error}</Message> : null}
      {overview ? (
        <>
          <section className="cards" aria-label="Summary">
            <article className="panel stat">
              <h2>Controls tested</h2>
              <p className="stat-value">
                {overview.controls_tested}
                <span> of {overview.control_count}</span>
              </p>
            </article>
            <article className="panel stat">
              <h2>Total exceptions</h2>
              <p className="stat-value">{overview.total_exceptions}</p>
            </article>
            <article className="panel stat">
              <h2>Workpapers by status</h2>
              <dl className="status-counts">
                <div>
                  <dt>Draft</dt>
                  <dd>{overview.workpapers_by_status.draft}</dd>
                </div>
                <div>
                  <dt>Reviewed</dt>
                  <dd>{overview.workpapers_by_status.reviewed}</dd>
                </div>
                <div>
                  <dt>Approved</dt>
                  <dd>{overview.workpapers_by_status.approved}</dd>
                </div>
              </dl>
            </article>
          </section>
          <OverviewCharts overview={overview} />
          <section className="panel">
            <h2>Controls</h2>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Control</th>
                    <th>Name</th>
                    <th>Exceptions</th>
                    <th>Dataset</th>
                    <th>Test</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.exceptions_by_control.map((row) => (
                    <tr key={row.control_id}>
                      <td>{row.control_id}</td>
                      <td>{row.name}</td>
                      <td>{row.exception_count}</td>
                      <td>{row.dataset_label ?? ""}</td>
                      <td>
                        <Link to={`/tests/${row.control_id}`}>Open</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel">
            <h2>Workpapers</h2>
            {overview.workpapers.length === 0 ? (
              <p className="meta">No workpapers yet. Open a test to draft one.</p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Workpaper</th>
                      <th>Control</th>
                      <th>Dataset</th>
                      <th>Status</th>
                      <th>Edited</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.workpapers.map((paper) => (
                      <tr key={paper.id}>
                        <td>
                          <Link to={`/workpapers/${paper.id}`}>{paper.id}</Link>
                        </td>
                        <td>{paper.control_id}</td>
                        <td>{paper.dataset_label ?? ""}</td>
                        <td>
                          <StatusBadge status={paper.status} />
                        </td>
                        <td>{formatWhen(paper.edited_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </>
  );
}

function messageFrom(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "The dashboard could not reach the API.";
}

function formatWhen(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
