import "@mantine/tiptap/styles.css";
import React, {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { Menu } from "@mantine/core";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Blockquote from "@tiptap/extension-blockquote";
import Highlight from "@tiptap/extension-highlight";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import TextAlign from "@tiptap/extension-text-align";
import { Color, TextStyle } from "@tiptap/extension-text-style";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { Placeholder } from "@tiptap/extensions";
import { RichTextEditor, useRichTextEditorContext } from "@mantine/tiptap";
import { IndentDecrease, IndentIncrease, MoreHorizontal } from "lucide-react";
import { BlockGutter } from "./block_gutter.jsx";

// The editor that had the focus last; the one toolbar acts on it.
let focused = null;
const listeners = new Set();
const editors = new WeakMap();

export function setFocused(editor) {
  if (focused !== editor) {
    focused = editor;
    listeners.forEach((listener) => listener());
  }
}

export function clearFocused(editor) {
  if (focused === editor) {
    setFocused(null);
  }
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const HOST = "aq-doc-editor-host";
const LINK = /^(https?:\/\/|mailto:)/i;

function extensions(placeholder) {
  return [
    StarterKit.configure({
      heading: { levels: [3, 4] },
      // A quote holds paragraphs only, as the content model does.
      blockquote: false,
      link: {
        openOnClick: false,
        autolink: true,
        defaultProtocol: "https",
        protocols: ["mailto"],
        isAllowedUri: (url, ctx) => ctx.defaultValidate(url) && LINK.test(url),
      },
    }),
    Blockquote.extend({ content: "paragraph+" }),
    TextStyle,
    Color,
    Highlight,
    Subscript,
    Superscript,
    TextAlign.configure({ types: ["heading", "paragraph"] }),
    TaskList,
    TaskItem.configure({ nested: true }),
    Placeholder.configure({ placeholder }),
  ];
}

// At the first or last line of a chapter the arrow keys go on in the next one.
function atEdge(view, down) {
  const { $head } = view.state.selection;
  if ($head.depth < 1 || !view.endOfTextblock(down ? "down" : "up")) {
    return false;
  }
  return down ? $head.after(1) === view.state.doc.content.size : $head.before(1) === 0;
}

function focusNeighbour(view, step) {
  const hosts = Array.from(document.querySelectorAll(`.${HOST}`));
  const index = hosts.indexOf(view.dom.closest(`.${HOST}`));
  for (let next = index + step; next >= 0 && next < hosts.length; next += step) {
    const editor = editors.get(hosts[next]);
    if (editor && !editor.isDestroyed && editor.isEditable) {
      editor.commands.focus(step > 0 ? "start" : "end");
      return true;
    }
  }
  return false;
}

function LiveEditor({
  content,
  editable,
  placeholder,
  gutterLabels,
  contentClassName,
  onUpdate,
  onBlur,
  onFocus,
  header,
  host,
}) {
  const editor = useEditor({
    extensions: extensions(placeholder),
    content,
    editable,
    editorProps: {
      handleKeyDown: (view, event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
          return false;
        }
        const down = event.key === "ArrowDown";
        return atEdge(view, down) && focusNeighbour(view, down ? 1 : -1);
      },
    },
    onUpdate: ({ editor: current }) => onUpdate && onUpdate(current.getHTML()),
    onBlur: ({ editor: current }) => onBlur && onBlur(current.getHTML()),
    onFocus: ({ editor: current }) => {
      setFocused(current);
      if (onFocus) {
        onFocus();
      }
    },
  });

  useEffect(() => {
    if (!editor || !host.current) {
      return undefined;
    }
    editors.set(host.current, editor);
    return () => clearFocused(editor);
  }, [editor, host]);

  useEffect(() => {
    // Only outside changes sync; while the person types the round trip
    // through the state would move the cursor to the start.
    if (!editor || editor.isDestroyed || editor.isFocused) {
      return;
    }
    if (content !== editor.getHTML()) {
      editor.commands.setContent(content, { emitUpdate: false });
    }
  }, [content, editor]);

  useEffect(() => {
    if (editor && editor.isEditable !== editable) {
      editor.setEditable(editable);
      listeners.forEach((listener) => listener());
    }
  }, [editable, editor]);

  if (!editor) {
    return null;
  }
  return (
    <RichTextEditor
      editor={editor}
      variant="subtle"
      withTypographyStyles={false}
      classNames={{ root: "aq-doc-editor", content: contentClassName }}
    >
      {header}
      <RichTextEditor.Content />
      <BlockGutter editor={editor} labels={gutterLabels} />
    </RichTextEditor>
  );
}

// The text of one chapter. It shows the stored HTML until it comes near the
// viewport, so long offers do not start dozens of editors at once.
export function ChapterEditor({
  content = "",
  editable = true,
  placeholder = "",
  gutterLabels = {},
  contentClassName,
  onUpdate,
  onBlur,
  onFocus,
  header,
}) {
  const host = useRef(null);
  const [near, setNear] = useState(false);

  useEffect(() => {
    if (near || !host.current) {
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "800px 0px" },
    );
    observer.observe(host.current);
    return () => observer.disconnect();
  }, [near]);

  return (
    <div ref={host} className={HOST}>
      {near ? (
        <LiveEditor
          content={content}
          editable={editable}
          placeholder={placeholder}
          gutterLabels={gutterLabels}
          contentClassName={contentClassName}
          onUpdate={onUpdate}
          onBlur={onBlur}
          onFocus={onFocus}
          header={header}
          host={host}
        />
      ) : (
        <>
          {header}
          {/* Server-rendered from the content model; every text is escaped. */}
          <div className={contentClassName} dangerouslySetInnerHTML={{ __html: content }} />
        </>
      )}
    </div>
  );
}

function ListStep({ label, lift, children }) {
  const { editor } = useRichTextEditorContext();
  const run = () => {
    if (!editor) {
      return;
    }
    const item = editor.isActive("taskItem") ? "taskItem" : "listItem";
    const chain = editor.chain().focus();
    (lift ? chain.liftListItem(item) : chain.sinkListItem(item)).run();
  };
  return (
    <RichTextEditor.Control aria-label={label} title={label} onClick={run}>
      {children}
    </RichTextEditor.Control>
  );
}

// The control groups of the toolbar, in the order they give way to "…".
function groups({ colors, indentLabel, outdentLabel }) {
  return [
    <>
      <RichTextEditor.Undo />
      <RichTextEditor.Redo />
    </>,
    <>
      <RichTextEditor.H3 />
      <RichTextEditor.H4 />
      <RichTextEditor.Blockquote />
      <RichTextEditor.CodeBlock />
    </>,
    <>
      <RichTextEditor.Bold />
      <RichTextEditor.Italic />
      <RichTextEditor.Underline />
      <RichTextEditor.Strikethrough />
      <RichTextEditor.Code />
      <RichTextEditor.Subscript />
      <RichTextEditor.Superscript />
      <RichTextEditor.ClearFormatting />
    </>,
    <>
      <RichTextEditor.ColorPicker colors={colors} />
      <RichTextEditor.UnsetColor />
      <RichTextEditor.Highlight />
    </>,
    <>
      <RichTextEditor.BulletList />
      <RichTextEditor.OrderedList />
      <RichTextEditor.TaskList />
      <ListStep label={indentLabel}>
        <IndentIncrease size={16} />
      </ListStep>
      <ListStep label={outdentLabel} lift>
        <IndentDecrease size={16} />
      </ListStep>
    </>,
    <>
      <RichTextEditor.AlignLeft />
      <RichTextEditor.AlignCenter />
      <RichTextEditor.AlignRight />
      <RichTextEditor.AlignJustify />
    </>,
    <>
      <RichTextEditor.Link />
      <RichTextEditor.Unlink />
      <RichTextEditor.Hr />
    </>,
  ];
}

const GAP = 6;
const MORE_WIDTH = 34;

// How many groups fit next to the "…" button; widths are measured once each.
function useFit(rowRef, widths, count) {
  const [shown, setShown] = useState(count);
  useLayoutEffect(() => {
    rowRef.current
      ?.querySelectorAll("[data-group]")
      .forEach((el) => (widths.current[Number(el.dataset.group)] = el.offsetWidth));
  });
  useEffect(() => {
    const row = rowRef.current;
    if (!row) {
      return undefined;
    }
    const fit = () => {
      const room = row.clientWidth;
      let used = 0;
      let fits = 0;
      for (let i = 0; i < count; i += 1) {
        const width = (widths.current[i] || 120) + GAP;
        const reserve = i < count - 1 ? MORE_WIDTH : 0;
        if (used + width + reserve > room) {
          break;
        }
        used += width;
        fits += 1;
      }
      setShown(fits);
    };
    const observer = new ResizeObserver(fit);
    observer.observe(row);
    fit();
    return () => observer.disconnect();
  }, [rowRef, widths, count]);
  return shown;
}

// The one formatting toolbar of the page (Confluence); it works on the text
// chapter that had the focus last. ``children`` are the AI actions.
export function ChapterToolbar({
  labels,
  colors = [],
  className,
  toolbarLabel,
  moreLabel,
  indentLabel,
  outdentLabel,
  children,
}) {
  const editor = useSyncExternalStore(subscribe, () => focused, () => null);
  const usable = Boolean(editor && !editor.isDestroyed && editor.isEditable);
  const all = groups({ colors, indentLabel, outdentLabel });
  const rowRef = useRef(null);
  const widths = useRef([]);
  const shown = useFit(rowRef, widths, all.length);
  const hidden = all.slice(shown);
  return (
    // A click here must not reach the page, which ends the selection.
    <div
      className={className}
      role="toolbar"
      aria-label={toolbarLabel}
      onClick={(event) => event.stopPropagation()}
    >
      <RichTextEditor
        editor={usable ? editor : null}
        variant="subtle"
        withTypographyStyles={false}
        labels={labels}
        classNames={{ root: "aq-doc-toolbar-editor" }}
      >
        <div ref={rowRef} className="aq-doc-format-row">
          <fieldset className="aq-doc-toolbar-fields" disabled={!usable}>
            {all.slice(0, shown).map((group, index) => (
              <RichTextEditor.ControlsGroup key={index} data-group={index}>
                {group}
              </RichTextEditor.ControlsGroup>
            ))}
          </fieldset>
          {/* Outside the fieldset: "…" also opens before a text has the focus. */}
          {hidden.length > 0 && (
            <Menu position="bottom-end" shadow="md" withinPortal zIndex={150}>
              <Menu.Target>
                <button
                  type="button"
                  className="aq-doc-toolbar-more"
                  aria-label={moreLabel}
                  title={moreLabel}
                >
                  <MoreHorizontal size={16} />
                </button>
              </Menu.Target>
              <Menu.Dropdown>
                <fieldset className="aq-doc-toolbar-fields" disabled={!usable}>
                  <div className="aq-doc-toolbar-overflow">
                    {hidden.map((group, index) => (
                      <RichTextEditor.ControlsGroup key={shown + index}>
                        {group}
                      </RichTextEditor.ControlsGroup>
                    ))}
                  </div>
                </fieldset>
              </Menu.Dropdown>
            </Menu>
          )}
        </div>
      </RichTextEditor>
      {children}
    </div>
  );
}
