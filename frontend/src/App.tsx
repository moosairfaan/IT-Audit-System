import { useEffect, useState } from "react";

type Health = {
  status: string;
  database: string;
};

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/health")
      .then((response) => (response.ok ? (response.json() as Promise<Health>) : Promise.reject()))
      .then((body) => {
        if (!cancelled) {
          setHealth(body);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUnavailable(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const database = unavailable ? "API unavailable" : health ? health.database : "Checking the database";

  return (
    <>
      <header>
        <p className="eyebrow">Financial services IT audit</p>
        <h1>The ITAudit System</h1>
      </header>
      <main>
        <p>
          Upload client populations, test IT general controls, and draft a workpaper for each test.
          The synthetic broker-dealer is loaded. Control tests, sample selection, and workpaper drafts run from the API.
        </p>
        <p className="status">Database: {database}</p>
      </main>
    </>
  );
}
