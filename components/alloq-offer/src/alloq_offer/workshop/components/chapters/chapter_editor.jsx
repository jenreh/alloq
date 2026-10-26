import "@mantine/tiptap/styles.css";
import React, { useEffect } from "react";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { RichTextEditor } from "@mantine/tiptap";

const CONTROLS = {
  bold: RichTextEditor.Bold,
  italic: RichTextEditor.Italic,
  h3: RichTextEditor.H3,
  h4: RichTextEditor.H4,
  bulletList: RichTextEditor.BulletList,
  orderedList: RichTextEditor.OrderedList,
  undo: RichTextEditor.Undo,
  redo: RichTextEditor.Redo,
};

// The editor of one chapter block. The formatting controls sit in the floating
// toolbar card together with the children (the module's own buttons); the
// text keeps the typography of the read-only document.
export function ChapterEditor({
  content = "",
  editable = true,
  onUpdate,
  onBlur,
  controlGroups = [],
  toolbarClassName,
  toolbarLabel,
  contentClassName,
  labels,
  header,
  children,
}) {
  const editor = useEditor({
    extensions: [
      // Only what a chapter can store: no quotes, code, rules or underlines.
      StarterKit.configure({
        link: false,
        heading: { levels: [3, 4] },
        blockquote: false,
        code: false,
        codeBlock: false,
        horizontalRule: false,
        strike: false,
        underline: false,
      }),
    ],
    content,
    editable,
    onUpdate: ({ editor: current }) => onUpdate && onUpdate(current.getHTML()),
    onBlur: ({ editor: current }) => onBlur && onBlur(current.getHTML()),
  });

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
    if (editor) {
      editor.setEditable(editable);
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
      labels={labels}
      classNames={{ root: "aq-doc-editor", content: contentClassName }}
    >
      <div className="aq-doc-float">
        <div className={toolbarClassName} role="toolbar" aria-label={toolbarLabel}>
          {editable && (
            <RichTextEditor.Toolbar className="aq-doc-controls">
              {controlGroups.map((group, index) => (
                <RichTextEditor.ControlsGroup key={index}>
                  {group.map((name) => {
                    const Control = CONTROLS[name];
                    return Control ? <Control key={name} /> : null;
                  })}
                </RichTextEditor.ControlsGroup>
              ))}
            </RichTextEditor.Toolbar>
          )}
          {children}
        </div>
      </div>
      {header}
      <RichTextEditor.Content />
    </RichTextEditor>
  );
}
