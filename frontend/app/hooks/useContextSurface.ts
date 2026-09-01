"use client";

import { useEffect, useRef, type RefObject } from "react";

type ContextSurfaceOptions = {
  active: boolean;
  onRequestClose: () => void;
  initialFocusRef?: RefObject<HTMLElement | null>;
};

/**
 * Shared behavior for a non-modal contextual surface such as an inspector or
 * Reader utility drawer. The owner remains responsible for restoring focus to
 * its trigger because it owns the trigger's lifecycle.
 */
export function useContextSurface<T extends HTMLElement>({
  active,
  onRequestClose,
  initialFocusRef,
}: ContextSurfaceOptions) {
  const surfaceRef = useRef<T | null>(null);
  const closeRef = useRef(onRequestClose);

  useEffect(() => {
    closeRef.current = onRequestClose;
  }, [onRequestClose]);

  useEffect(() => {
    if (!active) return;
    const frame = window.requestAnimationFrame(() => {
      (initialFocusRef?.current ?? surfaceRef.current)?.focus();
    });
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      event.preventDefault();
      closeRef.current();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [active, initialFocusRef]);

  return surfaceRef;
}
