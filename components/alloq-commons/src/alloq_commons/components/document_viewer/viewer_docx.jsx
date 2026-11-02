/* A Word document, rendered in the browser from bytes.
 *
 * The library's viewer is an editor held read-only: a source is evidence and
 * must not be changed here. The document is imported as a `File`, and the
 * rail previews are painted into canvases by `useDocxPageThumbnails`.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DocxEditorViewer,
  setWasmSource,
  useDocxEditor,
  useDocxPageThumbnails,
} from "@extend-ai/react-docx";
import docxWasmUrl from "@extend-ai/react-docx/docx_wasm_bg.wasm?url";

import { useDecoded } from "./viewer_bytes.js";
import { ViewerShell, withBoundary } from "./viewer_shell.jsx";

setWasmSource(docxWasmUrl);

const DOCX_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function DocxDocument({ encoded = "", fileName = "" }) {
  const bytes = useDecoded(encoded);
  const editor = useDocxEditor({ initialFileName: fileName });
  const [page, setPage] = useState(0);
  const root = useRef(null);
  const { thumbnails, paintThumbnail } = useDocxPageThumbnails(editor);

  useEffect(() => {
    if (!bytes) return;
    const file = new File([bytes], fileName || "dokument.docx", {
      type: DOCX_TYPE,
    });
    editor.importDocxFile(file);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bytes, fileName]);

  const renderThumb = useCallback(
    (item) => (
      <canvas
        className="aq-viewer-thumb-canvas"
        ref={(canvas) => paintThumbnail(item.index, canvas)}
      />
    ),
    [paintThumbnail],
  );

  const items = thumbnails.map((one) => ({
    index: one.pageIndex,
    number: one.pageNumber,
    /* Per page: a section break can turn one page landscape. */
    aspect: one.aspectRatio || null,
  }));

  /* The editor has no "go to page", so scroll our own page box by the measured
   * delta to the library's `data-docx-page-index` element. scrollIntoView
   * would also scroll the dialog. */
  const reveal = useCallback((index) => {
    setPage(index);
    const surface = root.current;
    const scroller = surface?.querySelector(".aq-viewer-page");
    const target = surface?.querySelector(`[data-docx-page-index="${index}"]`);
    if (!scroller || !target) return;
    scroller.scrollTop +=
      target.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
  }, []);

  if (!bytes) return null;

  return (
    <ViewerShell
      rootRef={root}
      items={items}
      active={page}
      onPick={reveal}
      renderThumb={renderThumb}
    >
      <DocxEditorViewer
        editor={editor}
        mode="read-only"
        className="aq-viewer-surface"
        onRequestPageReveal={setPage}
        pageBackgroundColor="var(--aq-viewer-sheet)"
        pageGapBackgroundColor="var(--aq-hover)"
      />
    </ViewerShell>
  );
}

export default withBoundary(DocxDocument);
