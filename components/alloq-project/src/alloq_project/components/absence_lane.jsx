import React, { useRef, useState } from "react";

const DAY_MS = 86400000;

function dayLabel(start, offset) {
  const d = new Date(start.getTime() + offset * DAY_MS);
  return `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.`;
}

function rangeLabel(start, from, to) {
  return from === to ? dayLabel(start, from) : `${dayLabel(start, from)}–${dayLabel(start, to)}`;
}

function workDays(from, to, holidays) {
  // The timeline starts on a Monday, so day % 7 < 5 is Monday to Friday.
  let count = 0;
  for (let day = from; day <= to; day += 1) {
    if (day % 7 < 5 && !holidays.includes(day)) count += 1;
  }
  return count;
}

/**
 * Timeline lane of one employee: dragging on its empty part selects a range of
 * whole days and reports it with onSelectRange(start, end). Bars and other
 * children keep their own clicks. Days before minDay cannot be selected.
 */
export function AbsenceLane({
  dayPx,
  days,
  minDay = 0,
  startIso,
  holidays = [],
  disabled = false,
  onSelectRange,
  children,
  className,
  style,
}) {
  const ref = useRef(null);
  const [drag, setDrag] = useState(null);
  const start = new Date(`${startIso}T00:00:00Z`);

  const dayAt = (clientX) => {
    const rect = ref.current.getBoundingClientRect();
    const day = Math.floor((clientX - rect.left) / dayPx);
    return Math.min(days - 1, Math.max(minDay, day));
  };

  const onPointerDown = (event) => {
    if (disabled || event.button !== 0 || event.target !== ref.current) return;
    if (minDay >= days) return;
    event.preventDefault();
    ref.current.setPointerCapture(event.pointerId);
    const day = dayAt(event.clientX);
    setDrag({ from: day, to: day });
  };

  const onPointerMove = (event) => {
    if (drag) setDrag({ from: drag.from, to: dayAt(event.clientX) });
  };

  const finish = (event, commit) => {
    if (!drag) return;
    if (ref.current.hasPointerCapture(event.pointerId)) {
      ref.current.releasePointerCapture(event.pointerId);
    }
    const from = Math.min(drag.from, drag.to);
    const to = Math.max(drag.from, drag.to);
    setDrag(null);
    if (commit && onSelectRange) onSelectRange(from, to);
  };

  const from = drag ? Math.min(drag.from, drag.to) : 0;
  const to = drag ? Math.max(drag.from, drag.to) : 0;

  return (
    <div
      ref={ref}
      className={className}
      style={{ ...style, cursor: disabled ? "default" : "crosshair", touchAction: "none" }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={(event) => finish(event, true)}
      onPointerCancel={(event) => finish(event, false)}
      onKeyDown={(event) => {
        if (event.key === "Escape" && drag) setDrag(null);
      }}
    >
      {children}
      {drag && (
        <>
          <div
            aria-hidden="true"
            style={{
              position: "absolute",
              top: 15,
              left: from * dayPx,
              width: (to - from + 1) * dayPx,
              height: 22,
              boxSizing: "border-box",
              border: "1.5px dashed var(--aq-accent)",
              borderRadius: 4,
              background: "var(--aq-accent-soft)",
              pointerEvents: "none",
              zIndex: 2,
            }}
          />
          <span
            role="status"
            style={{
              position: "absolute",
              top: 18,
              left: (to + 1) * dayPx + 6,
              fontSize: 11,
              fontWeight: 600,
              color: "var(--aq-accent)",
              whiteSpace: "nowrap",
              fontVariantNumeric: "tabular-nums",
              pointerEvents: "none",
              zIndex: 2,
            }}
          >
            {`${rangeLabel(start, from, to)} · ${workDays(from, to, holidays)} AT`}
          </span>
        </>
      )}
    </div>
  );
}
