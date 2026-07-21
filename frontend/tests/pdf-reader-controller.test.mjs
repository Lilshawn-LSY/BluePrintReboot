import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ZOOM,
  MAX_ZOOM,
  MIN_ZOOM,
  PdfReaderController,
} from "../app/lib/pdf/reader-controller.mjs";


function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}


function makeCanvas() {
  const context = { clearRectCalls: 0, clearRect() { this.clearRectCalls += 1; } };
  return { width: 0, height: 0, context, getContext: () => context };
}


function makeResolvedDocument({ numPages = 3, renderFactory } = {}) {
  const pages = [];
  const document = {
    numPages,
    getPageCalls: [],
    cleanupCalls: 0,
    destroyCalls: 0,
    async getPage(pageNumber) {
      this.getPageCalls.push(pageNumber);
      const page = {
        pageNumber,
        cleanupCalls: 0,
        getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale }),
        cleanup() { this.cleanupCalls += 1; },
        render(options) {
          assert.ok(options.canvasContext);
          assert.ok(options.viewport.width > 0);
          return renderFactory ? renderFactory(pageNumber) : { promise: Promise.resolve(), cancel() {} };
        },
      };
      pages.push(page);
      return page;
    },
    cleanup() { this.cleanupCalls += 1; },
    destroy() { this.destroyCalls += 1; },
  };
  return { document, pages };
}


function makeLoadingTask(document, promise = Promise.resolve(document)) {
  return {
    promise,
    destroyCalls: 0,
    async destroy() { this.destroyCalls += 1; },
  };
}


function makeController({ createLoadingTask, document, canvas = makeCanvas(), network, now } = {}) {
  const states = [];
  const diagnostics = [];
  const defaultDocument = document ?? makeResolvedDocument().document;
  const tasks = [];
  const controller = new PdfReaderController({
    createLoadingTask: createLoadingTask ?? (async () => {
      const task = makeLoadingTask(defaultDocument);
      tasks.push(task);
      return task;
    }),
    getCanvas: () => canvas,
    onState: (state) => states.push(state),
    onDiagnostics: (value) => diagnostics.push(value),
    getNetworkDiagnostics: () => network ?? {
      requestCount: 2,
      rangeRequestCount: 1,
      fullRequestCount: 1,
      requestMode: "range",
    },
    now,
  });
  return { controller, states, diagnostics, tasks, canvas, document: defaultDocument };
}


async function waitUntil(predicate) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setImmediate(resolve));
  }
  assert.fail("condition was not reached");
}


test("exposes loading before a successful document load and first-page render", async () => {
  const pending = deferred();
  const { document } = makeResolvedDocument({ numPages: 4 });
  const task = makeLoadingTask(document, pending.promise);
  const { controller, states } = makeController({ createLoadingTask: async () => task });

  const load = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => states.some((state) => state.mode === "loading"));
  assert.equal(controller.snapshot().mode, "loading");

  pending.resolve(document);
  await load;
  assert.deepEqual(controller.snapshot(), {
    mode: "ready",
    pageNumber: 1,
    totalPages: 4,
    zoom: 1,
    rendering: false,
    errorKind: null,
    message: "",
  });
  assert.deepEqual(document.getPageCalls, [1]);
  assert.equal(controller.diagnosticsSnapshot().documentLoadCount, 1);
  assert.equal(controller.diagnosticsSnapshot().renderCount, 1);
});


test("clamps previous, next, and direct page navigation without reloading the document", async () => {
  const { controller, document, tasks } = makeController();
  await controller.load("/api/blueprint/papers/fixture/pdf");

  await controller.previousPage();
  await controller.setPage(99);
  assert.equal(controller.snapshot().pageNumber, 3);
  await controller.nextPage();
  assert.equal(controller.snapshot().pageNumber, 3);
  await controller.setPage(-7);
  assert.equal(controller.snapshot().pageNumber, 1);

  assert.equal(tasks.length, 1);
  assert.equal(controller.diagnosticsSnapshot().documentLoadCount, 1);
  assert.deepEqual(document.getPageCalls, [1, 3, 1]);
});


test("bounds zoom and rerenders the page without recreating the loading task", async () => {
  const { controller, tasks } = makeController();
  await controller.load("/api/blueprint/papers/fixture/pdf");

  await controller.setZoom(0.01);
  assert.equal(controller.snapshot().zoom, MIN_ZOOM);
  await controller.setZoom(99);
  assert.equal(controller.snapshot().zoom, MAX_ZOOM);
  await controller.resetZoom();
  assert.equal(controller.snapshot().zoom, DEFAULT_ZOOM);

  assert.equal(tasks.length, 1);
  assert.equal(controller.diagnosticsSnapshot().documentLoadCount, 1);
  assert.equal(controller.diagnosticsSnapshot().renderCount, 4);
});


test("surfaces a safe unavailable state and retries from a clean load cycle", async () => {
  const { document } = makeResolvedDocument();
  const firstError = Object.assign(new Error("private upstream detail"), { status: 503 });
  const firstTask = makeLoadingTask(document, Promise.reject(firstError));
  const secondTask = makeLoadingTask(document);
  const created = [];
  const { controller } = makeController({
    createLoadingTask: async () => {
      const task = created.length === 0 ? firstTask : secondTask;
      created.push(task);
      return task;
    },
  });

  await controller.load("/api/blueprint/papers/fixture/pdf");
  assert.equal(controller.snapshot().mode, "error");
  assert.equal(controller.snapshot().errorKind, "unavailable");
  assert.doesNotMatch(controller.snapshot().message, /private upstream detail/);

  await controller.retry();
  assert.equal(controller.snapshot().mode, "ready");
  assert.equal(created.length, 2);
  assert.equal(controller.diagnosticsSnapshot().documentLoadCount, 2);
});


test("activates native fallback only after PDF.js cleanup and can retry PDF.js", async () => {
  const documents = [makeResolvedDocument().document, makeResolvedDocument().document];
  const tasks = documents.map((document) => makeLoadingTask(document));
  let index = 0;
  const { controller } = makeController({ createLoadingTask: async () => tasks[index++] });
  await controller.load("/api/blueprint/papers/fixture/pdf");

  await controller.activateFallback();
  assert.equal(controller.snapshot().mode, "fallback");
  assert.equal(tasks[0].destroyCalls, 1);
  assert.ok(documents[0].cleanupCalls >= 1);

  await controller.retry();
  assert.equal(controller.snapshot().mode, "ready");
  assert.equal(index, 2);
});


test("cleans the prior loading task and document when the managed paper URL changes", async () => {
  const documents = [makeResolvedDocument().document, makeResolvedDocument().document];
  const tasks = documents.map((document) => makeLoadingTask(document));
  let index = 0;
  const { controller } = makeController({ createLoadingTask: async () => tasks[index++] });

  await controller.load("/api/blueprint/papers/first/pdf");
  await controller.load("/api/blueprint/papers/second/pdf");

  assert.equal(controller.snapshot().mode, "ready");
  assert.equal(tasks[0].destroyCalls, 1);
  assert.ok(documents[0].cleanupCalls >= 1);
  assert.equal(controller.diagnosticsSnapshot().documentLoadCount, 2);
});


test("cancels an active stale render during rapid page navigation", async () => {
  const firstRender = deferred();
  let firstCancelCalls = 0;
  const { document } = makeResolvedDocument({
    renderFactory: (pageNumber) => pageNumber === 1
      ? {
          promise: firstRender.promise,
          cancel() {
            firstCancelCalls += 1;
            firstRender.reject(Object.assign(new Error("cancelled"), { name: "RenderingCancelledException" }));
          },
        }
      : { promise: Promise.resolve(), cancel() {} },
  });
  const { controller, tasks } = makeController({ document });

  const initialLoad = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => controller.diagnosticsSnapshot().renderCount === 1);
  await controller.nextPage();
  await initialLoad;

  assert.equal(firstCancelCalls, 1);
  assert.equal(controller.snapshot().pageNumber, 2);
  assert.equal(controller.snapshot().mode, "ready");
  assert.equal(controller.diagnosticsSnapshot().renderCancellationCount, 1);
  assert.equal(tasks.length, 1);
});


test("cleans a pending loading task on unmount without an unhandled rejection", async () => {
  const pending = deferred();
  const { document } = makeResolvedDocument();
  const task = makeLoadingTask(document, pending.promise);
  task.destroy = async function destroy() {
    this.destroyCalls += 1;
    pending.reject(Object.assign(new Error("aborted"), { name: "AbortException" }));
  };
  const { controller } = makeController({ createLoadingTask: async () => task });

  const load = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => controller.diagnosticsSnapshot().documentLoadCount === 1);
  await controller.destroy();
  await load;

  assert.equal(task.destroyCalls, 1);
});


test("records bounded diagnostics without document identity or content", async () => {
  const times = [10, 20, 25, 45];
  const { controller } = makeController({ now: () => times.shift() ?? 45 });
  await controller.load("/api/blueprint/papers/fixture/pdf");

  const diagnostics = controller.diagnosticsSnapshot();
  assert.equal(diagnostics.documentLoadDurationMs, 10);
  assert.equal(diagnostics.firstPageRenderDurationMs, 20);
  assert.equal(diagnostics.requestCount, 2);
  assert.equal(diagnostics.rangeRequestCount, 1);
  assert.equal(diagnostics.requestMode, "range");
  assert.deepEqual(Object.keys(diagnostics).sort(), [
    "documentLoadCount",
    "documentLoadDurationMs",
    "firstPageRenderDurationMs",
    "fullRequestCount",
    "rangeRequestCount",
    "renderCancellationCount",
    "renderCount",
    "requestCount",
    "requestMode",
  ]);
});
