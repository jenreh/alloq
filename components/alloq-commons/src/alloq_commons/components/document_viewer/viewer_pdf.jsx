/* A PDF, rendered in the browser from bytes with @embedpdf (pdfium in WASM).
 *
 * Two overrides must stay: the wasm comes from the bundle through Vite's
 * `?url` instead of the default CDN, and the font fallback is off, which the
 * library documents as "no external font requests". The desktop app is
 * offline, so a CDN fetch would break it.
 */

import { useCallback, useMemo } from "react";
import { createPluginRegistration } from "@embedpdf/core";
import { EmbedPDF } from "@embedpdf/core/react";
import { usePdfiumEngine } from "@embedpdf/engines/react";
import pdfiumWasmUrl from "@embedpdf/pdfium/pdfium.wasm?url";
import {
  DocumentContent,
  DocumentManagerPluginPackage,
  useActiveDocument,
  useOpenDocuments,
} from "@embedpdf/plugin-document-manager/react";
import { InteractionManagerPluginPackage } from "@embedpdf/plugin-interaction-manager/react";
import { RenderLayer, RenderPluginPackage } from "@embedpdf/plugin-render/react";
import { RotatePluginPackage, useRotate } from "@embedpdf/plugin-rotate/react";
import { ScrollPluginPackage, Scroller, useScroll } from "@embedpdf/plugin-scroll/react";
import {
  ThumbImg,
  ThumbnailPluginPackage,
  ThumbnailsPane,
} from "@embedpdf/plugin-thumbnail/react";
import { Viewport, ViewportPluginPackage } from "@embedpdf/plugin-viewport/react";
import { ZoomPluginPackage, useZoom } from "@embedpdf/plugin-zoom/react";

import { useBuffer } from "./viewer_bytes.js";
import { ViewerShell, withBoundary } from "./viewer_shell.jsx";

const NOT_OPENED = "Dieses PDF kann nicht geöffnet werden.";

function PdfDocument({ encoded = "", fileName = "" }) {
  const buffer = useBuffer(encoded);
  const { engine, error: engineError } = usePdfiumEngine({
    wasmUrl: pdfiumWasmUrl,
    fontFallback: null,
    /* The worker build resolves its wasm with import.meta.url from the Vite
     * dep cache, where the file is not, and then stays "loading" forever. */
    worker: false,
  });

  /* Memoised on the bytes: a fresh plugin array on every render rebuilds the
   * registry and the document never finishes opening. */
  const plugins = useMemo(
    () =>
      buffer
        ? [
            createPluginRegistration(DocumentManagerPluginPackage, {
              initialDocuments: [
                {
                  buffer,
                  name: fileName || "dokument.pdf",
                  autoActivate: true,
                },
              ],
            }),
            createPluginRegistration(ViewportPluginPackage),
            createPluginRegistration(ScrollPluginPackage),
            createPluginRegistration(RenderPluginPackage),
            createPluginRegistration(InteractionManagerPluginPackage),
            createPluginRegistration(ZoomPluginPackage),
            createPluginRegistration(RotatePluginPackage),
            /* The pane reserves each row from these numbers, so the rail CSS
             * must match them. */
            createPluginRegistration(ThumbnailPluginPackage, {
              width: 116,
              imagePadding: 14,
              labelHeight: 24,
              gap: 10,
              paddingY: 12,
            }),
          ]
        : null,
    [buffer, fileName],
  );

  if (engineError) {
    return <p className="aq-viewer-state">{NOT_OPENED}</p>;
  }
  if (!plugins || !engine) return null;

  return (
    <EmbedPDF engine={engine} plugins={plugins} autoMountDomElements={false}>
      <Opened fileName={fileName} />
    </EmbedPDF>
  );
}

export default withBoundary(PdfDocument);

/* The viewport refuses to register before the document is open;
 * DocumentContent is the library's gate for that. */
function Opened({ fileName }) {
  const { activeDocumentId } = useActiveDocument();
  const open = useOpenDocuments();

  /* autoActivate does not reliably mark the only document active before the
   * first render, so fall back to it. */
  const documentId = activeDocumentId ?? open[0]?.id ?? null;

  if (!documentId) return null;

  return (
    <DocumentContent documentId={documentId}>
      {({ documentState, isLoaded, isError }) => {
        if (isLoaded) return <Pages documentId={documentId} fileName={fileName} />;
        return (
          <p className="aq-viewer-state" data-status={documentState?.status}>
            {isError ? NOT_OPENED : "Wird geöffnet …"}
          </p>
        );
      }}
    </DocumentContent>
  );
}

function Pages({ documentId, fileName }) {
  const { state: scroll, provides: scroller } = useScroll(documentId);
  const { state: zoom, provides: zoomer } = useZoom(documentId);
  const { provides: rotator } = useRotate(documentId);

  const pick = useCallback(
    (index) => scroller?.scrollToPage({ pageNumber: index + 1 }),
    [scroller],
  );
  const onZoom = useCallback(
    (percent) => zoomer?.requestZoom(percent / 100),
    [zoomer],
  );
  const onRotate = useCallback(
    (degrees) => (degrees > 0 ? rotator?.rotateForward() : rotator?.rotateBackward()),
    [rotator],
  );

  const pages = scroll?.totalPages ?? 0;
  const page = (scroll?.currentPage ?? 1) - 1;

  /* The pane is virtualised: each row sits absolutely at the `top` the pane
   * computed. Without it every page lands at zero and only one shows. */
  const rail =
    pages > 1 ? (
      <ThumbnailsPane documentId={documentId} style={{ height: "100%" }}>
        {(meta) => (
          <div
            key={meta.pageIndex}
            style={{
              position: "absolute",
              top: meta.top,
              height: meta.wrapperHeight,
              width: "100%",
            }}
          >
            <button
              type="button"
              className="aq-viewer-thumb"
              aria-current={meta.pageIndex === page ? "true" : undefined}
              aria-label={`Seite ${meta.pageIndex + 1}`}
              onClick={() => pick(meta.pageIndex)}
              style={{ padding: meta.padding ?? 8 }}
            >
              <span
                className="aq-viewer-thumb-page"
                style={{ width: meta.width, height: meta.height }}
              >
                <ThumbImg meta={meta} documentId={documentId} />
              </span>
              <span
                className="aq-viewer-thumb-number"
                style={{
                  height: meta.labelHeight,
                  padding: 0,
                  lineHeight: `${meta.labelHeight}px`,
                }}
              >
                {meta.pageIndex + 1}
              </span>
            </button>
          </div>
        )}
      </ThumbnailsPane>
    ) : null;

  return (
    <ViewerShell
      pageCount={pages}
      active={page}
      onPick={pick}
      rail={rail}
      zoom={Math.round((zoom?.currentZoomLevel ?? 1) * 100)}
      onZoom={onZoom}
      onRotate={onRotate}
    >
      <Viewport documentId={documentId} style={{ height: "100%" }} aria-label={fileName}>
        <Scroller
          documentId={documentId}
          renderPage={({ width, height, pageIndex, scale }) => (
            /* RenderLayer paints only the content; the sheet draws the edge. */
            <div className="aq-viewer-sheet" style={{ width, height }}>
              <RenderLayer
                documentId={documentId}
                pageIndex={pageIndex}
                scale={scale}
                style={{ width: "100%", height: "100%", display: "block" }}
              />
            </div>
          )}
        />
      </Viewport>
    </ViewerShell>
  );
}
