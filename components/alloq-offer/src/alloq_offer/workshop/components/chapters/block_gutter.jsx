import React, { useCallback, useEffect, useRef, useState } from "react";
import { NodeSelection, TextSelection } from "@tiptap/pm/state";
import { GripVertical, Plus } from "lucide-react";

// Block types of the "+" picker and of "Umwandeln in"; ``run`` turns the block
// under the cursor into that type.
const TYPES = [
  ["paragraph", (c) => c.setParagraph()],
  ["heading3", (c) => c.setHeading({ level: 3 })],
  ["heading4", (c) => c.setHeading({ level: 4 })],
  ["bulletList", (c) => c.toggleBulletList()],
  ["orderedList", (c) => c.toggleOrderedList()],
  ["taskList", (c) => c.toggleTaskList()],
  ["blockquote", (c) => c.toggleBlockquote()],
  ["codeBlock", (c) => c.toggleCodeBlock()],
];
const ITEMS = new Set(["listItem", "taskItem"]);

// The block under the pointer: a list item inside a list, else a top-level node.
function blockAt(view, clientY) {
  const box = view.dom.getBoundingClientRect();
  const found = view.posAtCoords({ left: box.left + 12, top: clientY });
  if (!found) {
    return null;
  }
  const $pos = view.state.doc.resolve(found.inside >= 0 ? found.inside : found.pos);
  let depth = Math.min($pos.depth, 1);
  for (let d = $pos.depth; d > 0; d -= 1) {
    if (ITEMS.has($pos.node(d).type.name)) {
      depth = d;
      break;
    }
  }
  if (depth < 1) {
    return null;
  }
  const pos = $pos.before(depth);
  const dom = view.nodeDOM(pos);
  if (!(dom instanceof HTMLElement)) {
    return null;
  }
  return { pos, dom };
}

function selectInside(chain, pos) {
  return chain.command(({ tr }) => {
    tr.setSelection(TextSelection.near(tr.doc.resolve(pos + 1)));
    return true;
  });
}

// Notion's left gutter of a text chapter: "+" adds a block below and asks for
// its type, the grip drags the block and opens duplicate, delete and convert.
export function BlockGutter({ editor, labels = {} }) {
  const [block, setBlock] = useState(null);
  const [menu, setMenu] = useState(null);
  const gutterRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!editor || editor.isDestroyed) {
      return undefined;
    }
    const host = editor.view.dom.closest(".aq-doc-editor-host");
    if (!host) {
      return undefined;
    }
    const onMove = (event) => {
      if (!editor.isEditable || menu) {
        return;
      }
      if (gutterRef.current && gutterRef.current.contains(event.target)) {
        return;
      }
      const found = blockAt(editor.view, event.clientY);
      if (!found) {
        return;
      }
      const top = found.dom.getBoundingClientRect().top - host.getBoundingClientRect().top;
      // Only a different block re-renders the gutter.
      setBlock((shown) =>
        shown && shown.pos === found.pos && shown.top === top ? shown : { pos: found.pos, top },
      );
    };
    const onLeave = () => {
      if (!menu) {
        setBlock(null);
      }
    };
    host.addEventListener("mousemove", onMove);
    host.addEventListener("mouseleave", onLeave);
    return () => {
      host.removeEventListener("mousemove", onMove);
      host.removeEventListener("mouseleave", onLeave);
    };
  }, [editor, menu]);

  useEffect(() => {
    if (!menu) {
      return undefined;
    }
    const close = (event) => {
      if (event.type === "keydown" && event.key !== "Escape") {
        return;
      }
      if (event.type === "mousedown" && menuRef.current?.contains(event.target)) {
        return;
      }
      setMenu(null);
      if (event.type === "keydown") {
        editor.commands.focus();
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    menuRef.current?.querySelector("button")?.focus();
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menu, editor]);

  const node = useCallback(
    (pos) => (editor && !editor.isDestroyed ? editor.state.doc.nodeAt(pos) : null),
    [editor],
  );

  if (!editor || !editor.isEditable || !block) {
    return null;
  }

  const onDragStart = (event) => {
    const target = node(block.pos);
    if (!target) {
      return;
    }
    const { view } = editor;
    const selection = NodeSelection.create(view.state.doc, block.pos);
    view.dispatch(view.state.tr.setSelection(selection));
    const slice = selection.content();
    const { dom, text } = view.serializeForClipboard(slice);
    event.dataTransfer.clearData();
    event.dataTransfer.setData("text/html", dom.innerHTML);
    event.dataTransfer.setData("text/plain", text);
    event.dataTransfer.effectAllowed = "copyMove";
    const shown = view.nodeDOM(block.pos);
    if (shown instanceof HTMLElement) {
      event.dataTransfer.setDragImage(shown, 0, 0);
    }
    view.dragging = { slice, move: true };
  };

  const onAdd = () => {
    const target = node(block.pos);
    if (!target) {
      return;
    }
    // A list item gets its sibling; any other block a paragraph after it.
    const after = block.pos + target.nodeSize;
    const content = ITEMS.has(target.type.name)
      ? { type: target.type.name, content: [{ type: "paragraph" }] }
      : { type: "paragraph" };
    selectInside(editor.chain().insertContentAt(after, content), after).focus().run();
    const added = editor.view.nodeDOM(after);
    const host = editor.view.dom.closest(".aq-doc-editor-host");
    const top =
      added instanceof HTMLElement && host
        ? added.getBoundingClientRect().top - host.getBoundingClientRect().top
        : block.top + 28;
    setMenu({ pos: after, mode: "insert", top });
  };

  const convert = (run) => {
    const chain = selectInside(editor.chain().focus(), menu.pos).clearNodes();
    run(chain).run();
    setMenu(null);
  };

  const duplicate = () => {
    const target = node(menu.pos);
    if (target) {
      editor
        .chain()
        .focus()
        .insertContentAt(menu.pos + target.nodeSize, target.toJSON())
        .run();
    }
    setMenu(null);
  };

  const remove = () => {
    const target = node(menu.pos);
    if (target) {
      editor
        .chain()
        .focus()
        .deleteRange({ from: menu.pos, to: menu.pos + target.nodeSize })
        .run();
    }
    setMenu(null);
    setBlock(null);
  };

  return (
    <>
      <div
        ref={gutterRef}
        className="aq-doc-gutter"
        style={{ top: block.top }}
        contentEditable={false}
      >
        <button
          type="button"
          className="aq-doc-gutter-button"
          aria-label={labels.add}
          title={labels.add}
          onMouseDown={(event) => event.preventDefault()}
          onClick={onAdd}
        >
          <Plus size={16} />
        </button>
        <button
          type="button"
          className="aq-doc-gutter-button aq-doc-gutter-grip"
          aria-label={labels.grip}
          title={labels.grip}
          draggable
          onDragStart={onDragStart}
          onDragEnd={() => setBlock(null)}
          onMouseDown={(event) => event.stopPropagation()}
          onClick={() => setMenu({ pos: block.pos, mode: "actions", top: block.top })}
        >
          <GripVertical size={16} />
        </button>
      </div>
      {menu && (
        <div
          ref={menuRef}
          className="aq-doc-gutter-menu"
          role="menu"
          aria-label={menu.mode === "insert" ? labels.insertMenu : labels.actionsMenu}
          style={{ top: menu.top + 26 }}
          contentEditable={false}
        >
          {menu.mode === "actions" && (
            <>
              <button type="button" role="menuitem" onClick={duplicate}>
                {labels.duplicate}
              </button>
              <button type="button" role="menuitem" onClick={remove}>
                {labels.remove}
              </button>
              <div className="aq-doc-gutter-menu-title">{labels.convert}</div>
            </>
          )}
          {TYPES.map(([name, run]) => (
            <button key={name} type="button" role="menuitem" onClick={() => convert(run)}>
              {labels[name] || name}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
