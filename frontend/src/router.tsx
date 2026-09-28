import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Route =
  | { name: "overview" }
  | { name: "data" }
  | { name: "test"; controlId: string }
  | { name: "workpaper"; id: string };

type RouterValue = {
  path: string;
  route: Route;
  navigate: (to: string) => void;
};

const RouterContext = createContext<RouterValue | null>(null);

export function parseRoute(path: string): Route {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "data") {
    return { name: "data" };
  }
  if (parts[0] === "tests" && parts[1]) {
    return { name: "test", controlId: decodeURIComponent(parts[1]) };
  }
  if (parts[0] === "workpapers" && parts[1]) {
    return { name: "workpaper", id: decodeURIComponent(parts[1]) };
  }
  return { name: "overview" };
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = (to: string) => {
    window.history.pushState({}, "", to);
    setPath(window.location.pathname);
  };

  return (
    <RouterContext.Provider value={{ path, route: parseRoute(path), navigate }}>{children}</RouterContext.Provider>
  );
}

export function useRouter(): RouterValue {
  const value = useContext(RouterContext);
  if (!value) {
    throw new Error("Router is missing");
  }
  return value;
}

export function Link({ to, children, markCurrent = true }: { to: string; children: ReactNode; markCurrent?: boolean }) {
  const { navigate, path } = useRouter();
  return (
    <a
      href={to}
      aria-current={markCurrent && path === to ? "page" : undefined}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
          return;
        }
        event.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}
