import React, { useEffect, useRef, useState } from "react";
import { AlignCenter, AlignLeft, AlignRight, Trash2 } from "lucide-react";

const ALIGN_ICONS = { left: AlignLeft, center: AlignCenter, right: AlignRight };
const MIN_WIDTH = 10;
const CORNERS = ["nw", "ne", "sw", "se"];

// The picture of an image chapter (Confluence): a click selects it, the
// toolbar floats above, the corners resize it. ``children`` join the toolbar
// (replace upload). Width is a percentage of the page column.
export function ImageFrame({
  src = "",
  alt = "",
  width = 100,
  align = "center",
  editable = true,
  sizes = [],
  labels = {},
  onResize,
  onAlign,
  onRemove,
  children,
}) {
  const frame = useRef(null);
  const [selected, setSelected] = useState(false);
  const [drag, setDrag] = useState(null);
  const shown = drag ? drag.width : width;

  useEffect(() => {
    if (!selected) {
      return undefined;
    }
    const away = (event) => {
      if (!frame.current?.contains(event.target)) {
        setSelected(false);
      }
    };
    const escape = (event) => event.key === "Escape" && setSelected(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [selected]);

  useEffect(() => {
    if (!drag) {
      return undefined;
    }
    const move = (event) => {
      const column = frame.current.getBoundingClientRect().width || 1;
      const delta = (event.clientX - drag.x) * drag.direction;
      // A centered picture grows to both sides.
      const factor = align === "center" ? 2 : 1;
      const next = drag.start + ((delta * factor) / column) * 100;
      setDrag({ ...drag, width: Math.round(Math.min(100, Math.max(MIN_WIDTH, next))) });
    };
    const up = () => {
      if (onResize && drag.width !== width) {
        onResize(drag.width);
      }
      setDrag(null);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up, { once: true });
    return () => document.removeEventListener("mousemove", move);
  }, [drag, align, width, onResize]);

  const startDrag = (corner) => (event) => {
    event.preventDefault();
    event.stopPropagation();
    const direction = corner.endsWith("e") ? 1 : -1;
    setDrag({ x: event.clientX, start: width, width, direction });
  };

  return (
    <figure ref={frame} className="aq-doc-figure aq-doc-image-frame" data-align={align}>
      <div
        className="aq-doc-image-box"
        data-selected={selected ? "true" : "false"}
        style={{ width: `${shown}%` }}
      >
        {editable && selected && (
          <div
            className="aq-doc-image-toolbar"
            role="toolbar"
            aria-label={labels.toolbar}
          >
            {Object.entries(ALIGN_ICONS).map(([value, Icon]) => (
              <button
                key={value}
                type="button"
                className="aq-doc-image-tool"
                aria-label={labels[value]}
                title={labels[value]}
                aria-pressed={align === value}
                onClick={() => onAlign && onAlign(value)}
              >
                <Icon size={16} />
              </button>
            ))}
            <span className="aq-doc-toolbar-sep" />
            {sizes.map((size) => (
              <button
                key={size.value}
                type="button"
                className="aq-doc-image-tool aq-doc-image-size"
                aria-pressed={String(width) === size.value}
                onClick={() => onResize && onResize(Number(size.value))}
              >
                {size.label}
              </button>
            ))}
            <span className="aq-doc-toolbar-sep" />
            {children}
            <button
              type="button"
              className="aq-doc-image-tool"
              aria-label={labels.remove}
              title={labels.remove}
              onClick={() => onRemove && onRemove()}
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
        <button
          type="button"
          className="aq-doc-image-select"
          aria-label={labels.select}
          aria-pressed={selected}
          onClick={() => editable && setSelected(true)}
        >
          <img src={src} alt={alt} className="aq-doc-image" draggable={false} />
        </button>
        {editable &&
          selected &&
          CORNERS.map((corner) => (
            <span
              key={corner}
              className="aq-doc-image-corner"
              data-corner={corner}
              onMouseDown={startDrag(corner)}
            />
          ))}
        {drag && <span className="aq-doc-image-width">{drag.width} %</span>}
      </div>
    </figure>
  );
}
