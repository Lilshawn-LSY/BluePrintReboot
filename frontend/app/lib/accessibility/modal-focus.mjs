export const MODAL_FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function modalFocusableElements(dialog) {
  return Array.from(dialog?.querySelectorAll?.(MODAL_FOCUSABLE_SELECTOR) ?? [])
    .filter((element) => !element.hasAttribute?.("disabled"));
}

export function trapModalFocus(event, dialog) {
  if (event.key !== "Tab") return false;
  const focusable = modalFocusableElements(dialog);
  if (!focusable.length) {
    event.preventDefault();
    dialog?.focus?.();
    return true;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const activeElement = dialog?.ownerDocument?.activeElement;
  if (event.shiftKey ? activeElement === first || !dialog?.contains?.(activeElement) : activeElement === last || !dialog?.contains?.(activeElement)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
    return true;
  }
  return false;
}
