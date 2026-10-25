/**
 * Resizable columns for grids that are not an ExcelGrid (ExcelGrid takes
 * `resizeKey` itself). Renders a plain div that owns the column width variables.
 */
import React, { useRef } from "react";
import { useColumnResize } from "./column_resize.js";

export function ColumnResize({ id, className, storageKey, children }) {
  const rootRef = useRef(null);
  useColumnResize(rootRef, storageKey);
  return (
    <div id={id} ref={rootRef} className={className}>
      {children}
    </div>
  );
}
