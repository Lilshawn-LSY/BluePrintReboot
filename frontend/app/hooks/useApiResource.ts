"use client";

import { useEffect, useState } from "react";
import { ApiClientError } from "../lib/api/client";

export type ResourceState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "unavailable"; message: string }
  | { status: "not-found"; message: string }
  | { status: "error"; message: string };

export function useApiResource<T>(key: string, loader: () => Promise<T>): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T> & { resourceKey: string }>({ status: "loading", resourceKey: key });

  useEffect(() => {
    let active = true;
    loader()
      .then((data) => { if (active) setState({ status: "success", data, resourceKey: key }); })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiClientError) setState({ status: error.kind, message: error.message, resourceKey: key });
        else setState({ status: "error", message: "An unexpected frontend error occurred.", resourceKey: key });
      });
    return () => { active = false; };
    // Loaders are module-level API methods; the key explicitly controls refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (state.resourceKey !== key) return { status: "loading" };
  return state;
}
