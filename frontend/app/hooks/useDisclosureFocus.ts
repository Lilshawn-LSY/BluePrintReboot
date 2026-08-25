import { useRef } from "react";

/** Restores focus to a disclosure trigger after its temporary content closes. */
export function useDisclosureFocus<T extends HTMLElement>() {
  const triggerRef = useRef<T | null>(null);

  function restoreTriggerFocus() {
    requestAnimationFrame(() => triggerRef.current?.focus());
  }

  return { triggerRef, restoreTriggerFocus };
}
