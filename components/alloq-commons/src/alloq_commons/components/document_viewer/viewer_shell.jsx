/* The frame around a document: header, page rail and page.
 *
 * Ported from the mail-archive viewer kit. PDF, Word and PowerPoint get the
 * same header although three different renderers draw them. Every control is
 * optional: a renderer that cannot rotate gets no rotate button.
 *
 * The rail breakpoint measures the container, not the window, because the
 * viewer sits in a dialog. Colours live in `assets/css/aq-viewer.css`.
 */

import { Component, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Minus,
  PanelLeft,
  Plus,
  RotateCcw,
  RotateCw,
  Search,
  X,
} from "lucide-react";

const INLINE_MIN_WIDTH = 768;

const ZOOM_STEPS = [50, 75, 100, 125, 150, 200, 400];

/* The WASM parsers throw during render on a damaged file. Without a boundary
 * React unmounts the whole dialog; with it the file says it cannot be shown. */
export class ViewerBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error("The viewer could not read this file", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="aq-viewer-broken" role="status">
        <p>Diese Datei kann nicht angezeigt werden.</p>
        <p className="aq-viewer-broken-detail">
          {this.props.fileName
            ? `${this.props.fileName} ist beschädigt oder nutzt Funktionen, die die Vorschau nicht liest.`
            : "Die Datei ist beschädigt oder nutzt Funktionen, die die Vorschau nicht liest."}{" "}
          Der gelesene Text bleibt verfügbar.
        </p>
      </div>
    );
  }
}

/* Every viewer is exported through this, so none can ship without the boundary. */
export function withBoundary(Inner) {
  const Wrapped = (props) => (
    <ViewerBoundary fileName={props.fileName}>
      <Inner {...props} />
    </ViewerBoundary>
  );
  Wrapped.displayName = `WithBoundary(${Inner.displayName || Inner.name})`;
  return Wrapped;
}

export function useContainerWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const measure = () => {
      const next = element.getBoundingClientRect().width;
      /* A closing dialog measures zero; keep the last real width. */
      if (next === 0) return;
      setWidth(next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

function IconButton({ label, onClick, pressed, children }) {
  return (
    <button
      type="button"
      className="aq-viewer-icon"
      aria-label={label}
      title={label}
      aria-pressed={pressed === undefined ? undefined : String(pressed)}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function Divider() {
  return <span className="aq-viewer-divider" role="presentation" />;
}

/* Paints its preview only when first scrolled near, so a long document does
 * not rasterise every page on mount. */
function Thumb({ item, active, onPick, renderThumb, label }) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    if (seen || !ref.current) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((one) => one.isIntersecting)) setSeen(true);
      },
      { rootMargin: "200px" },
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [seen]);

  return (
    <button
      ref={ref}
      type="button"
      className="aq-viewer-thumb"
      aria-current={active ? "true" : undefined}
      aria-label={`${label} ${item.number}`}
      tabIndex={active ? 0 : -1}
      onClick={() => onPick(item.index)}
    >
      <span
        className="aq-viewer-thumb-page"
        style={item.aspect ? { aspectRatio: item.aspect } : undefined}
      >
        {seen ? renderThumb(item) : null}
      </span>
      <span className="aq-viewer-thumb-number">{item.number}</span>
    </button>
  );
}

export function ViewerShell({
  rootRef = null,
  items = null,
  pageCount = null,
  rail = null,
  active = 0,
  onPick = () => {},
  renderThumb = () => null,
  label = "Seite",
  railLabel = "Seiten",
  zoom = null,
  onZoom = null,
  onRotate = null,
  onSearch = null,
  extras = null,
  children,
}) {
  const [ref, width] = useContainerWidth();
  const inline = width >= INLINE_MIN_WIDTH;
  const [open, setOpen] = useState(true);
  const [query, setQuery] = useState(null);
  const railRef = useRef(null);

  /* Word and PowerPoint hand over a list of items; embedpdf brings its own
   * virtualised pane and hands over the whole rail. */
  const pages = pageCount ?? items?.length ?? 0;
  const hasRail = pages > 1;

  useEffect(() => setOpen(inline), [inline]);

  const showRail = hasRail && open;

  /* Roving tabindex: the rail is one tab stop and the arrows move within it. */
  const onKeyDown = useCallback(
    (event) => {
      const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[
        event.key
      ];
      if (!step) return;
      event.preventDefault();
      const next = Math.min(Math.max(active + step, 0), pages - 1);
      if (next !== active) onPick(next);
    },
    [active, pages, onPick],
  );

  useEffect(() => {
    railRef.current
      ?.querySelector('[aria-current="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const step = (by) => {
    /* "Fit width" can sit above the last step; findIndex is -1 there. */
    const found = ZOOM_STEPS.findIndex((one) => one >= zoom);
    const at = found === -1 ? ZOOM_STEPS.length : found;
    const next = ZOOM_STEPS[Math.min(Math.max(at + by, 0), ZOOM_STEPS.length - 1)];
    if (next !== zoom) onZoom(next);
  };

  /* Two refs on one node: the shell measures it, the Word viewer scrolls in it. */
  const attach = useCallback(
    (node) => {
      ref.current = node;
      if (rootRef) rootRef.current = node;
    },
    [ref, rootRef],
  );

  return (
    <div
      ref={attach}
      className="aq-viewer-shell"
      data-rail={showRail ? "open" : "closed"}
      data-rail-mode={inline ? "inline" : "overlay"}
    >
      <header className="aq-viewer-header">
        {hasRail ? (
          <IconButton
            label={showRail ? `${railLabel} ausblenden` : `${railLabel} einblenden`}
            pressed={showRail}
            onClick={() => setOpen((was) => !was)}
          >
            <PanelLeft size={18} strokeWidth={1.75} />
          </IconButton>
        ) : null}
        {pages ? (
          <p className="aq-viewer-count">
            {label} <b>{active + 1}</b> von {pages}
          </p>
        ) : null}

        <span className="aq-viewer-spacer" />

        {onRotate ? (
          <>
            <IconButton label="Nach links drehen" onClick={() => onRotate(-90)}>
              <RotateCcw size={18} strokeWidth={1.75} />
            </IconButton>
            <IconButton label="Nach rechts drehen" onClick={() => onRotate(90)}>
              <RotateCw size={18} strokeWidth={1.75} />
            </IconButton>
            <Divider />
          </>
        ) : null}

        {onZoom ? (
          <>
            <IconButton label="Verkleinern" onClick={() => step(-1)}>
              <Minus size={18} strokeWidth={1.75} />
            </IconButton>
            <span className="aq-viewer-zoom">
              <select
                aria-label="Zoom"
                value={ZOOM_STEPS.includes(zoom) ? zoom : ""}
                onChange={(event) => onZoom(Number(event.target.value))}
              >
                {ZOOM_STEPS.includes(zoom) ? null : (
                  <option value="">{Math.round(zoom)} %</option>
                )}
                {ZOOM_STEPS.map((one) => (
                  <option key={one} value={one}>
                    {one} %
                  </option>
                ))}
              </select>
              <ChevronDown size={14} strokeWidth={2} aria-hidden="true" />
            </span>
            <IconButton label="Vergrößern" onClick={() => step(1)}>
              <Plus size={18} strokeWidth={1.75} />
            </IconButton>
          </>
        ) : null}

        {onSearch ? (
          <>
            <Divider />
            {query === null ? (
              <IconButton label="In der Datei suchen" onClick={() => setQuery("")}>
                <Search size={18} strokeWidth={1.75} />
              </IconButton>
            ) : (
              <span className="aq-viewer-find">
                <Search size={15} strokeWidth={1.75} aria-hidden="true" />
                <input
                  autoFocus
                  type="search"
                  aria-label="In der Datei suchen"
                  placeholder="Suchen"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    onSearch(event.target.value);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      /* Escape closes the search, not the dialog. */
                      event.stopPropagation();
                      setQuery(null);
                      onSearch("");
                    }
                  }}
                />
                <button
                  type="button"
                  aria-label="Suche schließen"
                  onClick={() => {
                    setQuery(null);
                    onSearch("");
                  }}
                >
                  <X size={14} strokeWidth={2} />
                </button>
              </span>
            )}
          </>
        ) : null}

        {extras}
      </header>

      <div className="aq-viewer-body">
        {hasRail ? (
          <nav
            ref={railRef}
            className="aq-viewer-rail"
            /* A caller-supplied rail virtualises itself and owns its scrolling. */
            data-rail-kind={rail ? "pane" : "list"}
            aria-label={railLabel}
            onKeyDown={onKeyDown}
            hidden={!showRail}
          >
            {rail ??
              items?.map((one) => (
                <Thumb
                  key={one.index}
                  item={one}
                  active={one.index === active}
                  onPick={onPick}
                  renderThumb={renderThumb}
                  label={label}
                />
              ))}
          </nav>
        ) : null}
        {!inline && showRail ? (
          <div
            className="aq-viewer-scrim"
            role="presentation"
            onClick={() => setOpen(false)}
          />
        ) : null}
        <div className="aq-viewer-page">{children}</div>
      </div>
    </div>
  );
}
