export function initialCandidateReview() {
  return {
    status: "idle",
    collection: null,
    message: "Generate suggestions to begin an explicit review. Generation never applies Paper tags.",
  };
}

export function savedCandidateReviewReady(collection) {
  return {
    status: "ready",
    collection,
    message: collection.state === "generated"
      ? collection.items.length
        ? "Saved suggestions are ready to review. Nothing has been applied to this Paper."
        : "No saved suggestions are available for this Paper."
      : "Generate suggestions to begin an explicit review. Generation never applies Paper tags.",
  };
}

export function candidateReviewLoadFailure() {
  return {
    status: "error",
    collection: null,
    message: "Saved suggestions could not be loaded. No Paper tags were changed.",
  };
}

// A response may arrive after the Reader has changed Paper or after a newer
// explicit request has superseded it. Keep that response from changing the
// currently visible review state without coupling the UI to fetch internals.
export function createLatestPaperRequestGate() {
  let latestRequest = 0;
  let activePaperId = "";

  return {
    begin(paperId) {
      activePaperId = String(paperId);
      latestRequest += 1;
      return { paperId: activePaperId, requestId: latestRequest };
    },
    invalidate(paperId = activePaperId) {
      activePaperId = String(paperId);
      latestRequest += 1;
    },
    isCurrent(request) {
      return Boolean(
        request
        && request.requestId === latestRequest
        && request.paperId === activePaperId,
      );
    },
  };
}
