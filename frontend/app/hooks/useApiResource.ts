"use client";

import { useEffect, useState } from "react";
import { ApiClientError } from "../lib/api/client";

export type ResourceState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "unavailable"; message: string }
  | { status: "not-found"; message: string }
  | { status: "error"; message: string };

export type RetryableResourceState<T> = ResourceState<T> & { retry: () => void };

export function useApiResource<T>(key: string, loader: () => Promise<T>): RetryableResourceState<T> {
  const [attempt, setAttempt] = useState(0);
  const activeResourceKey = `${key}:${attempt}`;
  const [state, setState] = useState<ResourceState<T> & { resourceKey: string }>({ status: "loading", resourceKey: `${key}:0` });

  useEffect(() => {
    let active = true;
    loader()
      .then((data) => { if (active) setState({ status: "success", data, resourceKey: activeResourceKey }); })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiClientError) {
          const status = error.kind === "unavailable" || error.kind === "not-found"
            ? error.kind
            : "error";
          setState({ status, message: error.message, resourceKey: activeResourceKey });
        }
        else setState({ status: "error", message: "An unexpected frontend error occurred.", resourceKey: activeResourceKey });
      });
    return () => { active = false; };
    // Loaders are module-level API methods; the key explicitly controls refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const retry = () => setAttempt((current) => current + 1);
  if (state.resourceKey !== activeResourceKey) return { status: "loading", retry };
  if (state.status === "success") return { status: "success", data: state.data, retry };
  if (state.status === "loading") return { status: "loading", retry };
  return { status: state.status, message: state.message, retry };
}
