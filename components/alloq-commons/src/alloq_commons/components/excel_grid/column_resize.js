/**
 * Resizable grid columns: dragging a `data-col-resize="<key>"` handle inside the
 * root sets `--grid-col-<key>` on the root. Widths are kept per viewer in
 * localStorage under `storageKey`; a double click on a handle resets the column.
 * Without a storage key the hook does nothing.
 */
import { useEffect } from "react";
import { clampWidth, columnVar, loadWidths, saveWidths } from "./column_widths.js";

export function useColumnResize(rootRef, storageKey) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root || !storageKey) return undefined;
    const storage = window.localStorage;
    const widths = loadWidths(storage, storageKey);
    const apply = (col, width) => root.style.setProperty(columnVar(col), `${width}px`);
    Object.entries(widths).forEach(([col, width]) => apply(col, width));

    const handleOf = (e) => {
      const handle = e.target.closest?.("[data-col-resize]");
      return handle && root.contains(handle) ? handle : null;
    };

    const onPointerDown = (e) => {
      const handle = handleOf(e);
      if (!handle || e.button !== 0) return;
      e.preventDefault();
      const col = handle.getAttribute("data-col-resize");
      const startX = e.clientX;
      const startWidth = handle.parentElement.getBoundingClientRect().width;
      document.body.style.cursor = "col-resize";
      const move = (ev) => {
        widths[col] = clampWidth(startWidth + ev.clientX - startX);
        apply(col, widths[col]);
      };
      const up = () => {
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", up);
        document.body.style.cursor = "";
        saveWidths(storage, storageKey, widths);
      };
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", up);
    };

    const onDoubleClick = (e) => {
      const handle = handleOf(e);
      if (!handle) return;
      const col = handle.getAttribute("data-col-resize");
      delete widths[col];
      root.style.removeProperty(columnVar(col));
      saveWidths(storage, storageKey, widths);
    };

    root.addEventListener("pointerdown", onPointerDown);
    root.addEventListener("dblclick", onDoubleClick);
    return () => {
      root.removeEventListener("pointerdown", onPointerDown);
      root.removeEventListener("dblclick", onDoubleClick);
      Object.keys(widths).forEach((col) => root.style.removeProperty(columnVar(col)));
    };
  }, [rootRef, storageKey]);
}
