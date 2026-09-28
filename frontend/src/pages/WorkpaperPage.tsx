import { useEffect, useState } from "react";
import { ApiError, exportWorkpaper, getWorkpaper, updateWorkpaper } from "../api";
import { Message, StatusBadge } from "../components";
import { Link } from "../router";
import { SECTION_FIELDS, type Workpaper, type WorkpaperStatus } from "../types";

export function WorkpaperPage({ id }: { id: string }) {
  const workpaperId = Number(id);
  const valid = Number.isInteger(workpaperId) && workpaperId > 0;
  const [paper, setPaper] = useState<Workpaper | null>(null);
  const [sections, setSections] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "reviewed" | "approved" | "export" | null>(null);

  useEffect(() => {
    document.title = `Workpaper ${id} · The ITAudit System`;
  }, [id]);

  useEffect(() => {
    if (!valid) {
      return;
    }
    let cancelled = false;
    getWorkpaper(workpaperId)
      .then((body) => {
        if (!cancelled) {
          setPaper(body);
          setSections(body.sections);
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
  }, [valid, workpaperId]);

  async function persist(status?: WorkpaperStatus) {
    if (!paper) {
      return;
    }
    setBusy(status === "reviewed" || status === "approved" ? status : "save");
    setError(null);
    setNotice(null);
    try {
      const updated = await updateWorkpaper(workpaperId, status ? { sections, status } : { sections });
      setPaper(updated);
      setSections(updated.sections);
      setNotice(status === "approved" ? "Workpaper approved." : status === "reviewed" ? "Marked reviewed." : "Saved.");
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(null);
    }
  }

  async function download() {
    setBusy("export");
    setError(null);
    try {
      const markdown = await exportWorkpaper(workpaperId);
      const blob = new Blob([markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${paper?.control_id ?? "workpaper"}-${workpaperId}.md`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(null);
    }
  }

  if (!valid) {
    return <Message tone="error">Unknown workpaper.</Message>;
  }
  if (!paper && !error) {
    return <Message tone="loading">Loading workpaper {workpaperId}.</Message>;
  }
  if (!paper) {
    return <Message tone="error">{error}</Message>;
  }

  const locked = paper.status === "approved";

  return (
    <>
      <p className="crumbs">
        <Link to="/">Overview</Link>
        <span aria-hidden="true"> / </span>
        <Link to={`/tests/${paper.control_id}`}>{paper.control_id}</Link>
        <span aria-hidden="true"> / </span>
        Workpaper {paper.id}
      </p>
      <div className="page-heading">
        <div>
          <h1>Workpaper {paper.id}</h1>
          <p className="lede">
            {paper.control_id}, run {paper.run_id}
            {paper.sample_id ? `, sample ${paper.sample_id}` : ""}
            {paper.dataset_label ? `, ${paper.dataset_label}` : ""}.
          </p>
        </div>
        <StatusBadge status={paper.status} />
      </div>
      {locked ? <Message tone="note">This workpaper is approved and read-only.</Message> : null}
      {error ? <Message tone="error">{error}</Message> : null}
      {notice ? <Message tone="note">{notice}</Message> : null}
      <form
        className="workpaper"
        onSubmit={(event) => {
          event.preventDefault();
          void persist();
        }}
      >
        {SECTION_FIELDS.map(([key, title]) => (
          <label key={key}>
            {title}
            <textarea
              value={sections[key] ?? ""}
              readOnly={locked}
              rows={key === "exceptions_noted" || key === "procedure_performed" ? 6 : 4}
              onChange={(event) => setSections((current) => ({ ...current, [key]: event.target.value }))}
            />
          </label>
        ))}
        <div className="button-row">
          <button type="submit" className="primary" disabled={locked || busy !== null}>
            {busy === "save" ? "Saving" : "Save"}
          </button>
          <button type="button" disabled={locked || paper.status === "reviewed" || busy !== null} onClick={() => void persist("reviewed")}>
            {busy === "reviewed" ? "Marking reviewed" : "Mark reviewed"}
          </button>
          <button type="button" disabled={locked || busy !== null} onClick={() => void persist("approved")}>
            {busy === "approved" ? "Approving" : "Approve"}
          </button>
          <button type="button" disabled={busy !== null} onClick={() => void download()}>
            {busy === "export" ? "Exporting" : "Export markdown"}
          </button>
        </div>
      </form>
    </>
  );
}

function messageFrom(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "The workpaper could not be loaded.";
}
