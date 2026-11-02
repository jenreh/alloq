/* A PowerPoint deck, rendered in the browser from bytes.
 *
 * Props arrive camelCased (Python `file_name` is `fileName`). The wasm URL is
 * handed over explicitly because the library resolves it from the Vite dep
 * cache otherwise. The library's own toolbar and rail are off so the deck gets
 * the same header as PDF and Word.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ReactPptxViewer, setWasmSource } from "@extend-ai/react-pptx";
import "@extend-ai/react-pptx/styles.css";
import pptxWasmUrl from "@extend-ai/react-pptx/pptx_wasm_bg.wasm?url";

import { useDecoded } from "./viewer_bytes.js";
import { ViewerShell, withBoundary } from "./viewer_shell.jsx";

setWasmSource(pptxWasmUrl);

function PptxDeck({ encoded = "", fileName = "" }) {
  const source = useDecoded(encoded);
  const controller = useRef(null);
  const [slides, setSlides] = useState(0);
  const [aspect, setAspect] = useState(null);
  const [slide, setSlide] = useState(0);
  const [zoom, setZoom] = useState(100);

  /* `onLoad` hands over `{kind, document, warnings}`; slide size is in EMU, so
   * only the ratio is useful. */
  const onLoad = useCallback((presentation) => {
    const doc = presentation?.document;
    setSlides(doc?.slides?.length ?? 0);
    const size = doc?.size;
    setAspect(
      size?.widthEmu && size?.heightEmu ? size.widthEmu / size.heightEmu : null,
    );
  }, []);

  const renderThumb = useCallback(
    (item) => <SlideThumb controller={controller} index={item.index} />,
    [],
  );

  const pick = useCallback((index) => {
    setSlide(index);
    controller.current?.goToSlide(index);
  }, []);

  const zoomTo = useCallback((percent) => {
    setZoom(percent);
    controller.current?.setZoom(percent);
  }, []);

  const search = useCallback((query) => {
    if (!query) {
      controller.current?.clearSearchHighlights();
      return;
    }
    const [first] = controller.current?.search(query) ?? [];
    if (first) controller.current.highlightSearchResult(first);
  }, []);

  if (!source) return null;

  const items = Array.from({ length: slides }, (_, index) => ({
    index,
    number: index + 1,
    aspect,
  }));

  return (
    <ViewerShell
      label="Folie"
      railLabel="Folien"
      items={items}
      active={slide}
      onPick={pick}
      renderThumb={renderThumb}
      zoom={zoom}
      onZoom={zoomTo}
      onSearch={search}
    >
      <ReactPptxViewer
        ref={controller}
        source={source}
        aria-label={fileName}
        showToolbar={false}
        showThumbnails={false}
        slideIndex={slide}
        zoom={zoom}
        /* "contain" scales each slide to the viewport width and the zoom
         * applies on top, so 100 % is "fitted". The library knows only
         * "contain" and "none"; mail-archive's "width" falls back to none. */
        fitMode="contain"
        onLoad={onLoad}
        onSlideChange={setSlide}
        height="100%"
        style={{ height: "100%" }}
      />
    </ViewerShell>
  );
}

/* The controller paints into a node we own and returns its own teardown. */
function SlideThumb({ controller, index }) {
  const host = useRef(null);

  useEffect(() => {
    let release;
    let live = true;
    const node = host.current;
    if (!node || !controller.current) return undefined;
    controller.current
      .renderThumbnail(index, node)
      .then((teardown) => {
        if (live) release = teardown;
        else teardown?.();
      })
      .catch(() => {});
    return () => {
      live = false;
      release?.();
    };
  }, [controller, index]);

  return <span ref={host} className="aq-viewer-thumb-canvas" />;
}

export default withBoundary(PptxDeck);
