import { useEffect, useState, type FormEvent } from "react";
import { ApiError, createSample, generateWorkpaper, getControls, getLatestSample, getRuns, runTest } from "../api";
import { ExceptionTable, CompletenessTable, Message } from "../components";
import { Link, useRouter } from "../router";
import type { Control, Sample, TestRun } from "../types";

export function TestDetail({ controlId }: { controlId: string }) {
  const { navigate } = useRouter();
  const [control, setControl] = useState<Control | null>(null);
  const [run, setRun] = useState<TestRun | null>(null);
  const [sample, setSample] = useState<Sample | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [sampling, setSampling] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [method, setMethod] = useState<Sample["method"]>("random");
  const [sampleSize, setSampleSize] = useState("10");
  const [seed, setSeed] = useState("");
  const [attachSample, setAttachSample] = useState(true);

  useEffect(() => {
    document.title = `${controlId} · The ITAudit System`;
  }, [controlId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setMissing(false);
    setControl(null);
    setRun(null);
    setSample(null);
    Promise.all([getControls(), getRuns(), loadSample(controlId)])
      .then(([controls, runs, latest]) => {
        if (cancelled) {
          return;
        }
        const found = controls.find((item) => item.control_id === controlId) ?? null;
        setControl(found);
        setMissing(found === null);
        setRun(runs.find((item) => item.control_id === controlId) ?? null);
        setSample(latest);
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(messageFrom(caught));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [controlId]);

  async function onRun() {
    setRunning(true);
    setError(null);
    try {
      setRun(await runTest(controlId));
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setRunning(false);
    }
  }

  async function onSample(event: FormEvent) {
    event.preventDefault();
    const size = Number(sampleSize);
    if (!Number.isInteger(size) || size < 1) {
      setError("Sample size must be a whole number of at least 1.");
      return;
    }
    const parsedSeed = seed.trim() === "" ? null : Number(seed);
    if (parsedSeed !== null && !Number.isInteger(parsedSeed)) {
      setError("Seed must be a whole number, or left blank.");
      return;
    }
    setSampling(true);
    setError(null);
    try {
      setSample(await createSample(controlId, method, size, parsedSeed));
      setAttachSample(true);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setSampling(false);
    }
  }

  async function onDraft() {
    if (!run) {
      return;
    }
    setDrafting(true);
    setError(null);
    try {
      const sampleId = attachSample && sample ? sample.sample_id : null;
      const paper = await generateWorkpaper(controlId, run.run_id, sampleId);
      navigate(`/workpapers/${paper.id}`);
    } catch (caught) {
      setError(messageFrom(caught));
      setDrafting(false);
    }
  }

  if (loading) {
    return <Message tone="loading">Loading {controlId}.</Message>;
  }
  if (missing) {
    return <Message tone="error">Unknown control {controlId}.</Message>;
  }
  if (!control) {
    return error ? <Message tone="error">{error}</Message> : null;
  }

  return (
    <>
      <p className="crumbs">
        <Link to="/">Overview</Link>
        <span aria-hidden="true"> / </span>
        {control.control_id}
      </p>
      <div className="page-heading">
        <div>
          <h1>
            {control.control_id} {control.name}
          </h1>
        </div>
        <button type="button" className="primary" onClick={() => void onRun()} disabled={running}>
          {running ? "Running test" : "Run test"}
        </button>
      </div>
      {error ? <Message tone="error">{error}</Message> : null}
      <section className="panel definition">
        <h2>Control</h2>
        <dl>
          <div>
            <dt>Objective</dt>
            <dd>{control.objective}</dd>
          </div>
          <div>
            <dt>Risk addressed</dt>
            <dd>{control.risk_addressed}</dd>
          </div>
          <div>
            <dt>Population</dt>
            <dd>{capitalize(control.population)}</dd>
          </div>
          {run ? (
            <div>
              <dt>Latest run</dt>
              <dd>
                Population {run.population_count}. Exceptions {run.exception_count}. Run {run.run_id}.{" "}
                {run.dataset_label}.
              </dd>
            </div>
          ) : null}
        </dl>
        {run?.completeness ? (
          <div className="completeness">
            <h3>Completeness</h3>
            <CompletenessTable rows={[{ ...run.completeness, control_id: run.control_id, name: run.name }]} />
          </div>
        ) : null}
      </section>
      <section className="panel">
        <h2>Exceptions</h2>
        {run ? (
          run.exceptions.length === 0 ? (
            <p className="meta">No exceptions were noted.</p>
          ) : (
            <ExceptionTable rows={run.exceptions} />
          )
        ) : (
          <p className="meta">Run the test to load the exception table.</p>
        )}
      </section>
      <section className="panel">
        <h2>Sample</h2>
        <form className="sample-form" onSubmit={(event) => void onSample(event)}>
          <label>
            Method
            <select value={method} onChange={(event) => setMethod(event.target.value as Sample["method"])}>
              <option value="random">Random</option>
              <option value="risk_based">Risk-based</option>
            </select>
          </label>
          <label>
            Sample size
            <input value={sampleSize} onChange={(event) => setSampleSize(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Seed
            <input value={seed} onChange={(event) => setSeed(event.target.value)} inputMode="numeric" placeholder="Optional" />
          </label>
          <button type="submit" disabled={sampling || !run}>
            {sampling ? "Drawing sample" : "Generate sample"}
          </button>
        </form>
        {!run ? <p className="meta">Run the test before selecting a sample.</p> : null}
        {sample ? (
          <>
            <p className="meta">
              {sample.method === "risk_based" ? "Risk-based" : "Random"} sample of {sample.sample_size} from{" "}
              {sample.population_size}, seed {sample.seed}. Sample {sample.sample_id}. {sample.dataset_label}.
            </p>
            <div className="table-scroll sample-ids">
              <table>
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Selected ID</th>
                  </tr>
                </thead>
                <tbody>
                  {sample.selected_ids.map((itemId, index) => (
                    <tr key={`${itemId}-${index}`}>
                      <td>{index + 1}</td>
                      <td>{itemId}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : run ? (
          <p className="meta">No sample has been drawn.</p>
        ) : null}
      </section>
      <section className="panel actions-panel">
        <h2>Workpaper</h2>
        <label className="check">
          <input
            type="checkbox"
            checked={attachSample && sample !== null}
            disabled={!sample}
            onChange={(event) => setAttachSample(event.target.checked)}
          />
          Attach the sample shown above
        </label>
        <button type="button" className="primary" onClick={() => void onDraft()} disabled={!run || drafting}>
          {drafting ? "Drafting the workpaper" : "Generate workpaper"}
        </button>
      </section>
    </>
  );
}

async function loadSample(controlId: string): Promise<Sample | null> {
  try {
    return await getLatestSample(controlId);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      return null;
    }
    throw caught;
  }
}

function capitalize(value: string): string {
  if (!value) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function messageFrom(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "The test page could not reach the API.";
}
