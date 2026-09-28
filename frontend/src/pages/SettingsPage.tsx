import { useEffect, useState } from "react";
import { ApiError, getRules, saveRules } from "../api";
import { Message } from "../components";
import type { AuditRules, SodPair } from "../types";

export function SettingsPage() {
  const [rules, setRules] = useState<AuditRules | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Settings · The ITAudit System";
    getRules()
      .then(setRules)
      .catch((caught: unknown) => setError(messageFrom(caught)));
  }, []);

  async function save() {
    if (!rules) {
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setRules(await saveRules(rules));
      setNotice("Settings saved. The next test run uses these rules.");
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!rules && !error) {
    return <Message tone="loading">Loading settings.</Message>;
  }
  if (!rules) {
    return <Message tone="error">{error}</Message>;
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Settings</h1>
          <p className="lede">
            Privileged roles, critical systems, the dormancy threshold, and segregation-of-duties pairs. Defaults match the
            synthetic broker-dealer.
          </p>
        </div>
        <button type="button" className="primary" disabled={busy} onClick={() => void save()}>
          {busy ? "Saving" : "Save settings"}
        </button>
      </div>
      {error ? <Message tone="error">{error}</Message> : null}
      {notice ? <Message tone="note">{notice}</Message> : null}
      <section className="panel">
        <h2>Dormancy threshold</h2>
        <label>
          Days without a login
          <input
            type="number"
            min={1}
            value={rules.dormant_days}
            onChange={(event) => setRules({ ...rules, dormant_days: Number(event.target.value) })}
          />
        </label>
        <p className="meta">An active account is dormant when the last login is this many days before the as-of date, or missing.</p>
      </section>
      <NameList
        title="Privileged roles"
        hint="Risk-based sampling selects these roles first."
        values={rules.privileged_roles}
        onChange={(privileged_roles) => setRules({ ...rules, privileged_roles })}
      />
      <NameList
        title="Critical systems"
        hint="Risk-based sampling selects these systems first."
        values={rules.critical_systems}
        onChange={(critical_systems) => setRules({ ...rules, critical_systems })}
      />
      <section className="panel">
        <h2>Segregation-of-duties pairs</h2>
        <p className="meta">Holding both permissions is a conflict. ITGC-02 reads this list.</p>
        {rules.sod_pairs.map((pair, index) => (
          <div className="pair-row" key={`${pair.permission_a}-${index}`}>
            <label>
              Permission A
              <input
                aria-label={`Permission A ${index + 1}`}
                value={pair.permission_a}
                onChange={(event) => updatePair(rules, index, { permission_a: event.target.value }, setRules)}
              />
            </label>
            <label>
              Permission B
              <input
                aria-label={`Permission B ${index + 1}`}
                value={pair.permission_b}
                onChange={(event) => updatePair(rules, index, { permission_b: event.target.value }, setRules)}
              />
            </label>
            <label>
              Description
              <input
                aria-label={`Conflict description ${index + 1}`}
                value={pair.description}
                onChange={(event) => updatePair(rules, index, { description: event.target.value }, setRules)}
              />
            </label>
            <button type="button" onClick={() => setRules({ ...rules, sod_pairs: rules.sod_pairs.filter((_, item) => item !== index) })}>
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            setRules({
              ...rules,
              sod_pairs: [...rules.sod_pairs, { permission_a: "", permission_b: "", description: "" }],
            })
          }
        >
          Add pair
        </button>
      </section>
    </>
  );
}

function NameList({
  title,
  hint,
  values,
  onChange,
}: {
  title: string;
  hint: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="meta">{hint}</p>
      {values.map((value, index) => (
        <div className="pair-row" key={`${title}-${index}`}>
          <label>
            {title} {index + 1}
            <input
              aria-label={`${title} ${index + 1}`}
              value={value}
              onChange={(event) => onChange(values.map((item, itemIndex) => (itemIndex === index ? event.target.value : item)))}
            />
          </label>
          <button type="button" onClick={() => onChange(values.filter((_, item) => item !== index))}>
            Remove
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...values, ""])}>
        Add
      </button>
    </section>
  );
}

function updatePair(
  rules: AuditRules,
  index: number,
  patch: Partial<SodPair>,
  setRules: (rules: AuditRules) => void,
) {
  setRules({
    ...rules,
    sod_pairs: rules.sod_pairs.map((pair, item) => (item === index ? { ...pair, ...patch } : pair)),
  });
}

function messageFrom(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "Settings could not be saved.";
}
