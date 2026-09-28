import { useEffect, useState } from "react";
import { getDataSource } from "./api";
import { Message, Shell } from "./components";
import { DataPage } from "./pages/DataPage";
import { ImportWizard } from "./pages/ImportWizard";
import { Overview } from "./pages/Overview";
import { SettingsPage } from "./pages/SettingsPage";
import { TestDetail } from "./pages/TestDetail";
import { WorkpaperPage } from "./pages/WorkpaperPage";
import { RouterProvider, useRouter } from "./router";
import type { DataSource } from "./types";

export function App() {
  return (
    <RouterProvider>
      <Shell>
        <Routes />
      </Shell>
    </RouterProvider>
  );
}

function Routes() {
  const { route, path } = useRouter();
  if (route.name === "data") {
    return <DataPage />;
  }
  if (route.name === "import") {
    return <ImportGate />;
  }
  if (route.name === "settings") {
    return <SettingsPage />;
  }
  if (route.name === "test") {
    return <TestDetail controlId={route.controlId} />;
  }
  if (route.name === "workpaper") {
    return <WorkpaperPage id={route.id} />;
  }
  if (path !== "/") {
    return <Message tone="error">That page does not exist.</Message>;
  }
  return <Overview />;
}

function ImportGate() {
  const [source, setSource] = useState<DataSource | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDataSource()
      .then(setSource)
      .catch(() => setError("The import page could not reach the API."));
  }, []);

  if (error) {
    return <Message tone="error">{error}</Message>;
  }
  if (!source) {
    return <Message tone="loading">Loading import.</Message>;
  }
  if (!source.allow_real_data) {
    return <Message tone="note">Company data is turned off for this deployment.</Message>;
  }
  return <ImportWizard />;
}
