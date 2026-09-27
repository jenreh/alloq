import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  blockRect,
  boundingRect,
  fillHandleRect,
  findPos,
  formatNumber,
  move,
  normalizeRange,
  pageMove,
  parseNumber,
  parseTSV,
  planClear,
  planFill,
  planFillHandle,
  planPaste,
  rangeKeys,
  resolvePos,
  tabMove,
  toTSV,
  withBefore,
} from "../../src/alloq_commons/components/excel_grid/grid_logic.js";

// Two resources: emp-1 has projects A and B, emp-2 has project C; 3 weeks.
const WEEKS = ["w0", "w1", "w2"];
const row = (emp, code) => ({
  key: `${emp}|${code}`,
  block: emp,
  cells: WEEKS.map((w) => `${emp}|${code}|${w}`),
});
const layout = {
  rows: [row("emp-1", "A"), row("emp-1", "B"), row("emp-2", "C"), row("emp-3", "D")],
};

describe("move", () => {
  it("moves with arrows and clamps at edges", () => {
    assert.deepEqual(move(layout, { r: 0, c: 0 }, "up"), { r: 0, c: 0 });
    assert.deepEqual(move(layout, { r: 0, c: 0 }, "left"), { r: 0, c: 0 });
    assert.deepEqual(move(layout, { r: 0, c: 2 }, "right"), { r: 0, c: 2 });
    assert.deepEqual(move(layout, { r: 3, c: 1 }, "down"), { r: 3, c: 1 });
  });

  it("crosses from one resource to the next with ArrowDown", () => {
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "down"), { r: 2, c: 1 });
    assert.deepEqual(move(layout, { r: 2, c: 1 }, "up"), { r: 1, c: 1 });
  });

  it("Ctrl+Down jumps to block end, then to the end of the next block", () => {
    assert.deepEqual(move(layout, { r: 0, c: 0 }, "down", { ctrl: true }), { r: 1, c: 0 });
    assert.deepEqual(move(layout, { r: 1, c: 0 }, "down", { ctrl: true }), { r: 2, c: 0 });
    assert.deepEqual(move(layout, { r: 3, c: 0 }, "down", { ctrl: true }), { r: 3, c: 0 });
  });

  it("Ctrl+Up jumps to block start, then to the start of the previous block", () => {
    assert.deepEqual(move(layout, { r: 1, c: 0 }, "up", { ctrl: true }), { r: 0, c: 0 });
    assert.deepEqual(move(layout, { r: 2, c: 0 }, "up", { ctrl: true }), { r: 0, c: 0 });
    assert.deepEqual(move(layout, { r: 3, c: 0 }, "up", { ctrl: true }), { r: 2, c: 0 });
  });

  it("Ctrl+Left/Right and Home/End go to the row edges", () => {
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "right", { ctrl: true }), { r: 1, c: 2 });
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "left", { ctrl: true }), { r: 1, c: 0 });
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "home"), { r: 1, c: 0 });
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "end"), { r: 1, c: 2 });
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "home", { ctrl: true }), { r: 0, c: 0 });
    assert.deepEqual(move(layout, { r: 1, c: 1 }, "end", { ctrl: true }), { r: 3, c: 2 });
  });

  it("is a no-op on an empty layout", () => {
    assert.deepEqual(move({ rows: [] }, { r: 0, c: 0 }, "down"), { r: 0, c: 0 });
  });
});

describe("tabMove / pageMove", () => {
  it("wraps to the next and previous row", () => {
    assert.deepEqual(tabMove(layout, { r: 0, c: 2 }), { r: 1, c: 0 });
    assert.deepEqual(tabMove(layout, { r: 1, c: 0 }, true), { r: 0, c: 2 });
    assert.deepEqual(tabMove(layout, { r: 3, c: 2 }), { r: 3, c: 2 });
    assert.deepEqual(tabMove(layout, { r: 0, c: 0 }, true), { r: 0, c: 0 });
  });

  it("pages by the given number of rows", () => {
    assert.deepEqual(pageMove(layout, { r: 0, c: 1 }, 2), { r: 2, c: 1 });
    assert.deepEqual(pageMove(layout, { r: 1, c: 1 }, 10, true), { r: 0, c: 1 });
  });
});

describe("positions and ranges", () => {
  it("resolves keys, falling back to the block and then the first cell", () => {
    assert.deepEqual(resolvePos(layout, "emp-2|C|w2"), { r: 2, c: 2 });
    assert.deepEqual(resolvePos(layout, "emp-2|X|w2", "emp-2"), { r: 2, c: 0 });
    assert.deepEqual(resolvePos(layout, "gone", "gone"), { r: 0, c: 0 });
    assert.equal(resolvePos({ rows: [] }, "x"), null);
    assert.equal(findPos(layout, "nope"), null);
  });

  it("normalizes ranges and lists keys across resources", () => {
    const rect = normalizeRange({ r: 2, c: 1 }, { r: 1, c: 0 });
    assert.deepEqual(rect, { r0: 1, r1: 2, c0: 0, c1: 1 });
    assert.deepEqual(rangeKeys(layout, rect), [
      "emp-1|B|w0",
      "emp-1|B|w1",
      "emp-2|C|w0",
      "emp-2|C|w1",
    ]);
  });

  it("computes the bounding rect of positions", () => {
    assert.deepEqual(boundingRect([{ r: 2, c: 0 }, { r: 1, c: 2 }]), { r0: 1, r1: 2, c0: 0, c1: 2 });
  });

  it("selects the current resource block", () => {
    assert.deepEqual(blockRect(layout, 1), { r0: 0, r1: 1, c0: 0, c1: 2 });
  });
});

describe("numbers", () => {
  it("parses German and English decimals", () => {
    assert.equal(parseNumber("1,5"), 1.5);
    assert.equal(parseNumber(" 2.25 "), 2.25);
    assert.equal(parseNumber("1.234,5"), 1234.5);
    assert.equal(parseNumber("1,234.5"), 1234.5);
    assert.equal(parseNumber(",5"), 0.5);
    assert.equal(parseNumber("3"), 3);
    assert.equal(parseNumber("1,239"), 1.24);
    assert.equal(parseNumber(""), 0);
  });

  it("rejects invalid and negative input", () => {
    for (const bad of ["abc", "-1", "1,2,3x", "1..2", "1e3", "+"]) {
      assert.equal(parseNumber(bad), null, bad);
    }
  });

  it("honours min/max/decimals options", () => {
    assert.equal(parseNumber("-1,5", { min: -10 }), -1.5);
    assert.equal(parseNumber("8", { max: 7 }), null);
    assert.equal(parseNumber("1,26", { decimals: 1 }), 1.3);
    assert.equal(parseNumber("-0,001", { min: -1 }), 0);
  });

  it("formats with custom separator and decimals", () => {
    assert.equal(formatNumber(1.26, { decimals: 1, separator: "." }), "1.3");
    assert.equal(toTSV([[1.5]], { separator: "." }), "1.5");
  });

  it("formats in German without trailing zeros; zero is blank", () => {
    assert.equal(formatNumber(0), "");
    assert.equal(formatNumber(2), "2");
    assert.equal(formatNumber(1.5), "1,5");
    assert.equal(formatNumber(1.256), "1,26");
  });
});

describe("clipboard", () => {
  it("round-trips TSV", () => {
    const tsv = toTSV([
      [1, 0, 2.5],
      [0, 3, 0],
    ]);
    assert.equal(tsv, "1\t\t2,5\n\t3\t");
    assert.deepEqual(parseTSV(tsv + "\r\n"), [
      ["1", "", "2,5"],
      ["", "3", ""],
    ]);
  });

  it("pastes from the top-left and clips at the grid edge", () => {
    const rect = { r0: 3, r1: 3, c0: 1, c1: 1 };
    const { changes, skipped, rect: target } = planPaste(layout, rect, [["1", "2", "3"], ["4", "5", "6"]]);
    assert.deepEqual(changes, [
      { key: "emp-3|D|w1", value: 1 },
      { key: "emp-3|D|w2", value: 2 },
    ]);
    assert.equal(skipped, 0);
    assert.deepEqual(target, { r0: 3, r1: 3, c0: 1, c1: 2 });
  });

  it("fills a selection with a single value and counts invalid cells", () => {
    const rect = { r0: 0, r1: 1, c0: 0, c1: 1 };
    assert.equal(planPaste(layout, rect, [["2"]]).changes.length, 4);
    const res = planPaste(layout, { r0: 0, r1: 0, c0: 0, c1: 0 }, [["x", "1"]]);
    assert.equal(res.skipped, 1);
    assert.deepEqual(res.changes, [{ key: "emp-1|A|w1", value: 1 }]);
  });

  it("tiles a source across a selection that is an exact multiple", () => {
    const rect = { r0: 0, r1: 3, c0: 0, c1: 0 };
    const { changes } = planPaste(layout, rect, [["1"], ["2"]]);
    assert.deepEqual(
      changes.map((c) => c.value),
      [1, 2, 1, 2],
    );
  });

  it("returns nothing for an empty clipboard", () => {
    assert.deepEqual(planPaste(layout, { r0: 0, r1: 0, c0: 0, c1: 0 }, []).changes, []);
  });
});

describe("fill, clear and undo bookkeeping", () => {
  const values = { "emp-1|A|w0": 1, "emp-1|A|w1": 2, "emp-1|B|w0": 3 };
  const get = (k) => values[k] ?? 0;

  it("fills down from the first row", () => {
    const rect = { r0: 0, r1: 2, c0: 0, c1: 1 };
    assert.deepEqual(planFill(layout, rect, "down", get), [
      { key: "emp-1|B|w0", value: 1 },
      { key: "emp-1|B|w1", value: 2 },
      { key: "emp-2|C|w0", value: 1 },
      { key: "emp-2|C|w1", value: 2 },
    ]);
  });

  it("fills right from the first column", () => {
    const rect = { r0: 0, r1: 1, c0: 0, c1: 2 };
    assert.deepEqual(
      planFill(layout, rect, "right", get).map((c) => c.value),
      [1, 1, 3, 3],
    );
  });

  it("clears a range and drops no-op changes for undo", () => {
    const changes = planClear(layout, { r0: 0, r1: 1, c0: 0, c1: 0 });
    assert.deepEqual(withBefore(changes, get), [
      { key: "emp-1|A|w0", before: 1, after: 0 },
      { key: "emp-1|B|w0", before: 3, after: 0 },
    ]);
  });
});

describe("fill handle", () => {
  const rect = { r0: 1, r1: 1, c0: 1, c1: 1 };

  it("does nothing while the pointer stays inside the source", () => {
    assert.equal(fillHandleRect(rect, { r: 1, c: 1 }), null);
  });

  it("extends along the dominant axis only", () => {
    assert.deepEqual(fillHandleRect(rect, { r: 3, c: 2 }), { r0: 1, r1: 3, c0: 1, c1: 1 });
    assert.deepEqual(fillHandleRect(rect, { r: 2, c: 0 }), { r0: 1, r1: 2, c0: 1, c1: 1 });
    assert.deepEqual(fillHandleRect(rect, { r: 1, c: 2 }), { r0: 1, r1: 1, c0: 1, c1: 2 });
    assert.deepEqual(fillHandleRect(rect, { r: 0, c: 1 }), { r0: 0, r1: 1, c0: 1, c1: 1 });
    assert.deepEqual(fillHandleRect(rect, { r: 2, c: 2 }), { r0: 1, r1: 2, c0: 1, c1: 1 });
    assert.deepEqual(fillHandleRect(rect, { r: 1, c: 0 }), { r0: 1, r1: 1, c0: 0, c1: 1 });
  });

  it("copies a single value into every dragged-over cell", () => {
    const get = (k) => (k === "emp-1|A|w0" ? 5 : 0);
    const src = { r0: 0, r1: 0, c0: 0, c1: 0 };
    assert.deepEqual(planFillHandle(layout, src, { ...src, c1: 2 }, get), [
      { key: "emp-1|A|w1", value: 5 },
      { key: "emp-1|A|w2", value: 5 },
    ]);
    assert.deepEqual(
      planFillHandle(layout, src, { ...src, r1: 3 }, get).map((c) => c.key),
      ["emp-1|B|w0", "emp-2|C|w0", "emp-3|D|w0"],
    );
  });

  it("repeats a multi-cell source pattern, also upwards", () => {
    const values = { "emp-1|B|w0": 1, "emp-2|C|w0": 2 };
    const get = (k) => values[k] ?? 0;
    const src = { r0: 1, r1: 2, c0: 0, c1: 0 };
    assert.deepEqual(
      planFillHandle(layout, src, { ...src, r1: 3 }, get),
      [{ key: "emp-3|D|w0", value: 1 }],
    );
    assert.deepEqual(
      planFillHandle(layout, src, { ...src, r0: 0 }, get),
      [{ key: "emp-1|A|w0", value: 2 }],
    );
  });
});
