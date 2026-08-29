"use client";

import { useEffect, useRef, type RefObject } from "react";
import { modalFocusableElements, trapModalFocus } from "../lib/accessibility/modal-focus.mjs";

type ModalFocusOptions = {
  active: boolean;
  onRequestClose: () => void;
  initialFocusRef?: RefObject<HTMLElement | null>;
  restoreFocusRef?: RefObject<HTMLElement | null>;
};

/** Provides the shared keyboard behavior for temporary Reader dialogs. */
export function useModalFocus<T extends HTMLElement>({
  active,
  onRequestClose,
  initialFocusRef,
  restoreFocusRef,
}: ModalFocusOptions) {
  const dialogRef = useRef<T | null>(null);
  const closeRef = useRef(onRequestClose);

  useEffect(() => {
    closeRef.current = onRequestClose;
  }, [onRequestClose]);

  useEffect(() => {
    if (!active) return;
    const dialog = dialogRef.current;
    const initialTarget = initialFocusRef?.current;
    const restoreTarget = restoreFocusRef?.current;
    let frame = window.requestAnimationFrame(() => {
      (initialTarget ?? modalFocusableElements(dialog)[0] ?? dialog)?.focus();
    });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        closeRef.current();
        return;
      }
      if (trapModalFocus(event, dialog)) event.stopPropagation();
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown, true);
      frame = window.requestAnimationFrame(() => restoreTarget?.focus());
    };
  }, [active, initialFocusRef, restoreFocusRef]);

  return dialogRef;
}
