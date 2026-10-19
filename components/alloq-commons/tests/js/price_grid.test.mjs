import assert from "node:assert/strict";
import { it } from "node:test";
import * as G from "../../src/alloq_commons/components/excel_grid/grid_logic.js";

const layout = {
  rows: [{ key: "a", cells: ["la", "name", "cost", "formula"] }],
  specs: {
    la: { type: "text" }, name: { type: "text" },
    cost: { type: "decimal", max: 100000 },
    formula: { type: "decimal", readOnly: true },
  },
};
const rect = { r0: 0, r1: 0, c0: 0, c1: 0 };

it("pastes mixed text and precise money, skipping formulas", () => {
  const plan = G.planPaste(layout, rect, [["8030", "Data Scientist", "1.280,01 €", "1"]]);
  assert.deepEqual(plan.changes, [
    { key: "la", value: "8030" }, { key: "name", value: "Data Scientist" },
    { key: "cost", value: "1280.01" },
  ]);
  assert.equal(plan.skipped, 0);
});
it("clears only writable cells and preserves blank rather than zero", () => {
  assert.deepEqual(G.planClear(layout, { ...rect, c1: 3 }), [
    { key: "la", value: "" }, { key: "name", value: "" }, { key: "cost", value: "" },
  ]);
});
it("validates fill/undo batches and cannot write a formula", () => {
  assert.deepEqual(G.prepareChanges(layout, [
    { key: "formula", value: "12" }, { key: "cost", value: "-1" },
    { key: "name", value: "Junior" },
  ]).changes, [{ key: "name", value: "Junior" }]);
});
it("strict decimal parsing never drops signs or rounds excessive decimals", () => {
  for (const raw of ["NaN", "Infinity", "-1", "abc", "1.2345", "1,2,3", "0", "100001"]) {
    assert.equal(G.parseCell(raw, { type: "decimal", max: 100000 }), null, raw);
  }
  assert.equal(G.parseCell("1.000", { type: "decimal" }), "1000.00");
  assert.equal(G.parseCell("0,01", { type: "decimal" }), "0.01");
  assert.equal(G.parseCell("", { type: "decimal" }), "");
});
it("copies text, blank and decimal cells without converting labels to numbers", () => {
  assert.equal(G.formatCell("Senior", { type: "text" }), "Senior");
  assert.equal(G.formatCell("1280.01", { type: "decimal" }), "1280,01");
  assert.equal(G.formatCell("", { type: "decimal" }), "");
});
