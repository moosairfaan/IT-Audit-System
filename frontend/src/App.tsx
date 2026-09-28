import { Shell } from "./components";
import { DataPage } from "./pages/DataPage";
import { Overview } from "./pages/Overview";
import { TestDetail } from "./pages/TestDetail";
import { WorkpaperPage } from "./pages/WorkpaperPage";
import { RouterProvider, useRouter } from "./router";

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
  const { route } = useRouter();
  if (route.name === "data") {
    return <DataPage />;
  }
  if (route.name === "test") {
    return <TestDetail controlId={route.controlId} />;
  }
  if (route.name === "workpaper") {
    return <WorkpaperPage id={route.id} />;
  }
  return <Overview />;
}
