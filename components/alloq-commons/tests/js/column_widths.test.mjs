import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  MAX_WIDTH,
  MIN_WIDTH,
  clampWidth,
  columnVar,
  loadWidths,
  saveWidths,
} from "../../src/alloq_commons/components/excel_grid/column_widths.js";

function memoryStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = value;
    },
  };
}

describe("column widths", () => {
  it("names the CSS variable after the column key", () => {
    assert.equal(columnVar("12"), "--grid-col-12");
  });

  it("keeps a width between the limits and rounds it", () => {
    assert.equal(clampWidth(10), MIN_WIDTH);
    assert.equal(clampWidth(5000), MAX_WIDTH);
    assert.equal(clampWidth(240.6), 241);
    assert.equal(clampWidth(90, 80, 100), 90);
  });

  it("loads stored widths and ignores broken data", () => {
    const storage = memoryStorage({
      good: JSON.stringify({ a: 200, b: "wide" }),
      list: "[1,2]",
      broken: "{",
    });
    assert.deepEqual(loadWidths(storage, "good"), { a: 200 });
    assert.deepEqual(loadWidths(storage, "list"), {});
    assert.deepEqual(loadWidths(storage, "broken"), {});
    assert.deepEqual(loadWidths(storage, "missing"), {});
    assert.deepEqual(loadWidths(storage, ""), {});
  });

  it("saves widths and survives a failing storage", () => {
    const storage = memoryStorage();
    saveWidths(storage, "k", { a: 300 });
    assert.equal(storage.data.k, '{"a":300}');
    saveWidths(storage, "", { a: 1 });
    assert.deepEqual(Object.keys(storage.data), ["k"]);
    const failing = {
      setItem: () => {
        throw new Error("full");
      },
    };
    assert.doesNotThrow(() => saveWidths(failing, "k", {}));
  });
});
