import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ZOOM,
  MAX_ZOOM,
  MIN_ZOOM,
  PdfReaderController,
  canvasRenderGeometry,
} from "../app/lib/pdf/reader-controller.mjs";
import { normalizePageSelection } from "../app/lib/pdf/selection-coordinates.mjs";


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
  return { width: 0, height: 0, style: { width: "", height: "" }, context, getContext: () => context };
}


function makeTextLayerContainer() {
  const properties = new Map();
  return {
    children: [],
    attributes: new Map(),
    style: {
      width: "",
      height: "",
      setProperty(name, value) { properties.set(name, value); },
      removeProperty(name) { properties.delete(name); },
      getPropertyValue(name) { return properties.get(name) ?? ""; },
    },
    replaceChildren(...children) { this.children = children; },
    removeAttribute(name) { this.attributes.delete(name); },
  };
}


function makeResolvedDocument({ numPages = 3, renderFactory } = {}) {
  const pages = [];
  const renderOptions = [];
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
        getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale, scale, rotation: 0 }),
        cleanup() { this.cleanupCalls += 1; },
        render(options) {
          assert.ok(options.canvasContext);
          assert.ok(options.viewport.width > 0);
          renderOptions.push({ pageNumber, ...options });
          return renderFactory ? renderFactory(pageNumber) : { promise: Promise.resolve(), cancel() {} };
        },
      };
      pages.push(page);
      return page;
    },
    cleanup() { this.cleanupCalls += 1; },
    destroy() { this.destroyCalls += 1; },
  };
  return { document, pages, renderOptions };
}


function makeLoadingTask(document, promise = Promise.resolve(document)) {
  return {
    promise,
    destroyCalls: 0,
    async destroy() { this.destroyCalls += 1; },
  };
}


function makeController({
  createLoadingTask,
  createTextLayer,
  document,
  canvas = makeCanvas(),
  textLayerContainer = makeTextLayerContainer(),
  getOutputScale,
  network,
  now,
} = {}) {
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
    createTextLayer,
    getCanvas: () => canvas,
    getTextLayerContainer: () => textLayerContainer,
    getOutputScale,
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
  return { controller, states, diagnostics, tasks, canvas, textLayerContainer, document: defaultDocument };
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


test("sizes the backing canvas for DPR while preserving logical viewport dimensions", async () => {
  for (const dpr of [1, 1.25, 1.5, 2]) {
    const resolved = makeResolvedDocument();
    const { controller, canvas } = makeController({
      document: resolved.document,
      getOutputScale: () => dpr,
    });

    await controller.load("/api/blueprint/papers/fixture/pdf");

    assert.equal(canvas.width, Math.ceil(600 * dpr));
    assert.equal(canvas.height, Math.ceil(800 * dpr));
    assert.equal(canvas.style.width, "600px");
    assert.equal(canvas.style.height, "800px");
    assert.deepEqual(resolved.renderOptions[0].transform, dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0]);
    assert.equal(controller.snapshot().zoom, DEFAULT_ZOOM);
  }
});


test("keeps zoom semantics independent of DPR and reuses the loaded document", async () => {
  let dpr = 1.25;
  const resolved = makeResolvedDocument();
  const { controller, canvas, tasks } = makeController({
    document: resolved.document,
    getOutputScale: () => dpr,
  });
  await controller.load("/api/blueprint/papers/fixture/pdf");

  dpr = 2;
  await controller.setZoom(1.5);

  assert.equal(controller.snapshot().zoom, 1.5);
  assert.equal(canvas.style.width, "900px");
  assert.equal(canvas.style.height, "1200px");
  assert.equal(canvas.width, 1800);
  assert.equal(canvas.height, 2400);
  assert.equal(tasks.length, 1);
  assert.equal(controller.diagnosticsSnapshot().documentLoadCount, 1);
});


test("bounds invalid and excessive output scales", () => {
  assert.deepEqual(canvasRenderGeometry({ width: 600, height: 800 }, 0.5), {
    cssWidth: 600,
    cssHeight: 800,
    canvasWidth: 600,
    canvasHeight: 800,
    outputScale: 1,
    transform: undefined,
  });
  assert.equal(canvasRenderGeometry({ width: 600, height: 800 }, 4).outputScale, 2);
});


test("renders selectable text with the same page and zoom viewport", async () => {
  const textLayerRenders = [];
  const createTextLayer = async ({ page, container, viewport }) => ({
    async render() {
      const textNode = { textContent: `Selectable page ${page.pageNumber}` };
      container.replaceChildren(textNode);
      textLayerRenders.push({ pageNumber: page.pageNumber, scale: viewport.width / 600 });
    },
    cancel() {},
  });
  const { controller, textLayerContainer, tasks } = makeController({ createTextLayer });

  await controller.load("/api/blueprint/papers/fixture/pdf");
  assert.equal(textLayerContainer.children[0].textContent, "Selectable page 1");
  await controller.nextPage();
  assert.equal(textLayerContainer.children[0].textContent, "Selectable page 2");
  await controller.setZoom(1.5);
  assert.equal(textLayerContainer.children[0].textContent, "Selectable page 2");
  assert.deepEqual(textLayerRenders, [
    { pageNumber: 1, scale: 1 },
    { pageNumber: 2, scale: 1 },
    { pageNumber: 2, scale: 1.5 },
  ]);
  assert.equal(textLayerContainer.style.getPropertyValue("--total-scale-factor"), "1.5");
  assert.equal(tasks.length, 1);
});


test("cancels and removes a stale text layer during repeated navigation", async () => {
  const firstTextRender = deferred();
  let firstTextRenderStarted = false;
  let cancelCalls = 0;
  const createTextLayer = async ({ page, container }) => ({
    render() {
      if (page.pageNumber === 1) {
        firstTextRenderStarted = true;
        return firstTextRender.promise;
      }
      container.replaceChildren({ textContent: `page ${page.pageNumber}` });
      return Promise.resolve();
    },
    cancel() {
      cancelCalls += 1;
      if (page.pageNumber === 1) {
        firstTextRender.reject(Object.assign(new Error("cancelled"), { name: "AbortException" }));
      }
    },
  });
  const { controller, textLayerContainer } = makeController({ createTextLayer });

  const initialLoad = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => firstTextRenderStarted);
  await controller.nextPage();
  await initialLoad;

  assert.ok(cancelCalls >= 1);
  assert.equal(textLayerContainer.children.length, 1);
  assert.equal(textLayerContainer.children[0].textContent, "page 2");
  assert.equal(controller.snapshot().pageNumber, 2);
  assert.equal(controller.snapshot().mode, "ready");
});


test("normalizes selection geometry independently of DPR and zoom", () => {
  const baseline = normalizePageSelection({
    pageNumber: 2,
    text: " selected text ",
    pageRect: { left: 10, top: 20, width: 600, height: 800 },
    selectionRects: [{ left: 70, top: 100, right: 250, bottom: 140 }],
  });

  for (const scale of [1.25, 1.5, 2, 3]) {
    assert.deepEqual(normalizePageSelection({
      pageNumber: 2,
      text: "selected text",
      pageRect: { left: 10, top: 20, width: 600 * scale, height: 800 * scale },
      selectionRects: [{
        left: 10 + (60 * scale),
        top: 20 + (80 * scale),
        right: 10 + (240 * scale),
        bottom: 20 + (120 * scale),
      }],
    }), baseline);
  }
  assert.deepEqual(baseline, {
    pageNumber: 2,
    text: "selected text",
    coordinateSpace: "page-normalized",
    rectangles: [{ x: 0.1, y: 0.1, width: 0.3, height: 0.05 }],
  });
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
  const textLayerContainer = makeTextLayerContainer();
  const { controller, canvas } = makeController({
    createLoadingTask: async () => tasks[index++],
    createTextLayer: async ({ container }) => ({
      async render() { container.replaceChildren({ textContent: "selectable" }); },
      cancel() {},
    }),
    textLayerContainer,
  });
  await controller.load("/api/blueprint/papers/fixture/pdf");

  await controller.activateFallback();
  assert.equal(controller.snapshot().mode, "fallback");
  assert.equal(tasks[0].destroyCalls, 1);
  assert.ok(documents[0].cleanupCalls >= 1);
  assert.equal(canvas.width, 0);
  assert.equal(canvas.height, 0);
  assert.equal(textLayerContainer.children.length, 0);

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

test("strict-mode-like cleanup cannot clear or corrupt the replacement controller", async () => {
  const sharedCanvas = makeCanvas();
  const firstDocumentPending = deferred();
  const firstDestroyPending = deferred();
  const { document: firstDocument } = makeResolvedDocument();
  const firstTask = makeLoadingTask(firstDocument, firstDocumentPending.promise);
  firstTask.destroy = async function destroy() {
    this.destroyCalls += 1;
    firstDocumentPending.reject(Object.assign(new Error("intentional cleanup"), { name: "AbortException" }));
    await firstDestroyPending.promise;
  };
  const { document: secondDocument } = makeResolvedDocument({ numPages: 5 });
  const secondTask = makeLoadingTask(secondDocument);
  const firstStates = [];
  const secondStates = [];
  let currentController = null;
  let firstController;
  let secondController;

  firstController = new PdfReaderController({
    createLoadingTask: async () => firstTask,
    getCanvas: () => sharedCanvas,
    isCurrent: () => currentController === firstController,
    onState: (state) => firstStates.push(state),
  });
  currentController = firstController;
  const firstLoad = firstController.load("/api/blueprint/papers/fixture-a/pdf");
  await waitUntil(() => firstController.diagnosticsSnapshot().documentLoadCount === 1);
  const firstCleanup = firstController.destroy();

  secondController = new PdfReaderController({
    createLoadingTask: async () => secondTask,
    getCanvas: () => sharedCanvas,
    isCurrent: () => currentController === secondController,
    onState: (state) => secondStates.push(state),
  });
  currentController = secondController;
  await secondController.load("/api/blueprint/papers/fixture-b/pdf");
  assert.equal(secondController.snapshot().mode, "ready");
  assert.equal(secondController.snapshot().totalPages, 5);
  assert.deepEqual(secondDocument.getPageCalls, [1]);
  assert.equal(sharedCanvas.width, 600);
  assert.equal(sharedCanvas.height, 800);

  firstDestroyPending.resolve();
  await Promise.all([firstCleanup, firstLoad]);
  assert.equal(firstTask.destroyCalls, 1);
  assert.equal(secondTask.destroyCalls, 0);
  assert.equal(secondController.snapshot().mode, "ready");
  assert.equal(sharedCanvas.width, 600);
  assert.equal(sharedCanvas.height, 800);
  assert.equal(firstStates.some((state) => state.mode === "error"), false);
  assert.equal(secondStates.at(-1).mode, "ready");
});


test("destroy waits for asynchronous loading-task creation and disposes the obsolete task", async () => {
  const creationPending = deferred();
  const documentPending = deferred();
  const { document } = makeResolvedDocument();
  const task = makeLoadingTask(document, documentPending.promise);
  task.destroy = async function destroy() {
    this.destroyCalls += 1;
    documentPending.reject(Object.assign(new Error("intentional cleanup"), { name: "AbortException" }));
  };
  const states = [];
  const { controller } = makeController({
    createLoadingTask: () => creationPending.promise,
  });
  controller.onState = (state) => states.push(state);

  const load = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => controller.diagnosticsSnapshot().documentLoadCount === 1);
  let destroySettled = false;
  const destroy = controller.destroy().then(() => {
    destroySettled = true;
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(destroySettled, false);

  creationPending.resolve(task);
  await Promise.all([destroy, load]);
  assert.equal(task.destroyCalls, 1);
  assert.equal(states.some((state) => state.mode === "error"), false);
});


test("destroy observes a pending loading-task cancellation without a user-visible error", async () => {
  const documentPending = deferred();
  const { document } = makeResolvedDocument();
  const task = makeLoadingTask(document, documentPending.promise);
  task.destroy = async function destroy() {
    this.destroyCalls += 1;
    documentPending.reject(Object.assign(new Error("intentional cleanup"), { name: "AbortException" }));
  };
  const { controller, states } = makeController({ createLoadingTask: async () => task });

  const load = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => controller.diagnosticsSnapshot().documentLoadCount === 1);
  await Promise.all([controller.destroy(), load]);

  assert.equal(task.destroyCalls, 1);
  assert.equal(states.some((state) => state.mode === "error"), false);
});


test("retry cancels the prior operation and starts one new authoritative load", async () => {
  const firstDocumentPending = deferred();
  const { document: firstDocument } = makeResolvedDocument();
  const { document: secondDocument } = makeResolvedDocument({ numPages: 7 });
  const firstTask = makeLoadingTask(firstDocument, firstDocumentPending.promise);
  firstTask.destroy = async function destroy() {
    this.destroyCalls += 1;
    firstDocumentPending.reject(Object.assign(new Error("superseded"), { name: "AbortException" }));
  };
  const secondTask = makeLoadingTask(secondDocument);
  const created = [];
  const { controller } = makeController({
    createLoadingTask: async () => {
      const task = created.length === 0 ? firstTask : secondTask;
      created.push(task);
      return task;
    },
  });

  const firstLoad = controller.load("/api/blueprint/papers/fixture/pdf");
  await waitUntil(() => created.length === 1);
  await Promise.all([controller.retry(), firstLoad]);

  assert.equal(created.length, 2);
  assert.equal(firstTask.destroyCalls, 1);
  assert.equal(secondTask.destroyCalls, 0);
  assert.equal(controller.snapshot().mode, "ready");
  assert.equal(controller.snapshot().totalPages, 7);
  assert.deepEqual(secondDocument.getPageCalls, [1]);
});


test("paper change cancels old work and unmount cleans only the new paper operation", async () => {
  const firstDocumentPending = deferred();
  const { document: firstDocument } = makeResolvedDocument();
  const { document: secondDocument } = makeResolvedDocument({ numPages: 6 });
  const firstTask = makeLoadingTask(firstDocument, firstDocumentPending.promise);
  firstTask.destroy = async function destroy() {
    this.destroyCalls += 1;
    firstDocumentPending.reject(Object.assign(new Error("paper changed"), { name: "AbortException" }));
  };
  const secondTask = makeLoadingTask(secondDocument);
  const createdUrls = [];
  const { controller, states } = makeController({
    createLoadingTask: async (url) => {
      createdUrls.push(url);
      return createdUrls.length === 1 ? firstTask : secondTask;
    },
  });

  const firstLoad = controller.load("/api/blueprint/papers/first/pdf");
  await waitUntil(() => createdUrls.length === 1);
  await Promise.all([
    controller.load("/api/blueprint/papers/second/pdf"),
    firstLoad,
  ]);
  assert.deepEqual(createdUrls, [
    "/api/blueprint/papers/first/pdf",
    "/api/blueprint/papers/second/pdf",
  ]);
  assert.equal(firstTask.destroyCalls, 1);
  assert.equal(secondTask.destroyCalls, 0);
  assert.equal(controller.snapshot().mode, "ready");
  assert.equal(controller.snapshot().totalPages, 6);
  assert.equal(states.at(-1).totalPages, 6);

  await controller.destroy();
  assert.equal(firstTask.destroyCalls, 1);
  assert.equal(secondTask.destroyCalls, 1);
  await controller.retry();
  assert.equal(createdUrls.length, 2);
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
