import assert from "node:assert/strict";
import test from "node:test";

import { collectAllPaginatedItems } from "../app/lib/api/pagination.mjs";
import { createExclusiveMutationGate } from "../app/lib/reader/mutation-coordinator.mjs";

test("pagination collects entities beyond the first 100 without skipping", async () => {
  const source = Array.from({ length: 235 }, (_, index) => `item-${index}`);
  const calls = [];
  const items = await collectAllPaginatedItems(async ({ limit, offset }) => {
    calls.push({ limit, offset });
    const pageItems = source.slice(offset, offset + limit);
    return {
      items: pageItems,
      total: source.length,
      has_more: offset + pageItems.length < source.length,
    };
  });

  assert.deepEqual(items, source);
  assert.deepEqual(calls, [
    { limit: 100, offset: 0 },
    { limit: 100, offset: 100 },
    { limit: 100, offset: 200 },
  ]);
});

test("pagination rejects a collection that changes between pages", async () => {
  let call = 0;
  await assert.rejects(
    collectAllPaginatedItems(async () => {
      call += 1;
      return call === 1
        ? { items: ["first"], total: 2, has_more: true }
        : { items: ["second"], total: 3, has_more: false };
    }, 1),
    /changed while it was being loaded/,
  );
});

test("Reader mutation gate rejects overlap and only its owner can release it", () => {
  const gate = createExclusiveMutationGate();
  const first = gate.tryAcquire();

  assert.equal(typeof first, "number");
  assert.equal(gate.isActive(), true);
  assert.equal(gate.tryAcquire(), null);
  assert.equal(gate.release(Number(first) + 1), false);
  assert.equal(gate.isActive(), true);
  assert.equal(gate.release(first), true);
  assert.equal(gate.isActive(), false);
  assert.notEqual(gate.tryAcquire(), null);
});
