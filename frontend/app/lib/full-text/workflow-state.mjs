export function initialFullTextUiState() {
  return {
    phase: "loading",
    data: null,
    content: "",
    viewerOpen: false,
    message: "",
  };
}


export function transitionFullTextUiState(state, event) {
  switch (event.type) {
    case "status-loading":
      return { ...state, phase: "loading", message: "" };
    case "status-loaded":
      return { ...state, phase: "ready", data: event.status, message: "" };
    case "operation-started":
      return { ...state, phase: "working", message: "" };
    case "document-loaded":
      return {
        ...state,
        phase: "ready",
        data: event.document,
        content: event.document.content,
        viewerOpen: Boolean(event.open),
        message: "",
      };
    case "operation-failed":
      return { ...state, phase: "error", message: event.message || "Full text could not be loaded." };
    case "viewer-closed":
      return { ...state, viewerOpen: false };
    default:
      return state;
  }
}
