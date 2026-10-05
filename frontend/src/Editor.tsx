import { useEffect, useRef, type CSSProperties } from 'react';
import type { WritingFocusPreferences } from './experimental/writingFocusClient';
import { EditorContent, useEditor, type JSONContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';

// BACKPORT CANDIDATE (U13): manuscript prose is text, never an HTML template.
export function proseDocument(content: string): JSONContent {
  return { type: 'doc', content: content.split('\n').map(text => ({
    type: 'paragraph', ...(text ? { content: [{ type: 'text', text }] } : {}),
  })) };
}

// Coordinate contract shared with workspace search: text blocks separated by
// one newline, hardBreak represented by one newline, Unicode codepoints counted.
export function editorAnchorText(doc: any, from: number, to: number): string {
  return doc.textBetween(from, to, '\n', (node: any) => node.type.name === 'hardBreak' ? '\n' : '');
}

type Props = {
  writingPreferences?: WritingFocusPreferences;
  content: string;
  document?: JSONContent;
  onChange: (value: string, document?: JSONContent) => void;
  onSelection?: (selection: { from: number; to: number; text: string }) => void;
  onCompositionChange?: (composing: boolean) => void;
  onAnchorChange?: (anchor: { offset: number; scroll: number }) => void;
  restoreAnchor?: { requestId: number; offset: number; scroll: number };
};

export function ChapterEditor(props: Props) {
  const callbacks = useRef(props);
  callbacks.current = props;
  const composing = useRef(false);
  const compositionEnd = useRef<ReturnType<typeof setTimeout>>();
  const emitted = useRef<JSONContent>();
  const appliedAnchor = useRef<number>();
  const editor = useEditor({
    extensions: [StarterKit, Placeholder.configure({ placeholder: '从这里开始写作…' })],
    content: props.document ?? proseDocument(props.content),
    editorProps: {
      attributes: { role: 'textbox', 'aria-label': '章节正文', 'aria-multiline': 'true' },
      handleDOMEvents: {
        compositionstart: () => {
          clearTimeout(compositionEnd.current);
          composing.current = true;
          callbacks.current.onCompositionChange?.(true);
          return false;
        },
        compositionend: view => {
          // Let ProseMirror consume the final native input first. Never replay a
          // deferred external document over the text just committed by the IME.
          compositionEnd.current = setTimeout(() => {
            if (view.isDestroyed) return;
            composing.current = false;
            emitted.current = view.state.doc.toJSON();
            callbacks.current.onChange(editorAnchorText(view.state.doc, 0, view.state.doc.content.size), emitted.current);
            callbacks.current.onCompositionChange?.(false);
          }, 0);
          return false;
        },
      },
    },
    onUpdate: ({ editor }) => {
      emitted.current = editor.getJSON();
      callbacks.current.onChange(editor.getText({ blockSeparator: '\n' }), emitted.current);
    },
    onSelectionUpdate: ({ editor }) => {
      const { from, to } = editor.state.selection;
      callbacks.current.onSelection?.({ from, to, text: editorAnchorText(editor.state.doc, from, to) });
      if (callbacks.current.onAnchorChange) callbacks.current.onAnchorChange({
        offset: Array.from(editorAnchorText(editor.state.doc, 0, from)).length,
        scroll: editor.view.dom.closest('.main-workspace')?.scrollTop || 0,
      });
    },
  });
  useEffect(() => {
    if (!editor || composing.current || editor.view.composing) return;
    // A controlled echo is already in ProseMirror. Rebuilding it would reset
    // selection/undo and can interrupt Chinese composition on every keystroke.
    if (props.document && props.document === emitted.current) return;
    const next = props.document ?? proseDocument(props.content);
    if (JSON.stringify(editor.getJSON()) !== JSON.stringify(next)) editor.commands.setContent(next, false);
  }, [props.document, props.content, editor]);
  useEffect(() => {
    if (!editor || !props.onAnchorChange) return;
    const scroller = editor.view.dom.closest('.main-workspace');
    const capture = () => callbacks.current.onAnchorChange?.({
      offset: Array.from(editorAnchorText(editor.state.doc, 0, editor.state.selection.from)).length,
      scroll: scroller?.scrollTop || 0,
    });
    capture();
    scroller?.addEventListener('scroll', capture, { passive: true });
    return () => scroller?.removeEventListener('scroll', capture);
  }, [editor, Boolean(props.onAnchorChange)]);
  useEffect(() => {
    const anchor = props.restoreAnchor;
    if (!editor || !anchor || appliedAnchor.current === anchor.requestId || composing.current || editor.view.composing) return;
    const fullText = editorAnchorText(editor.state.doc, 0, editor.state.doc.content.size);
    const utf16 = Array.from(fullText).slice(0, Math.max(0, anchor.offset)).join('').length;
    let low = 0, high = editor.state.doc.content.size;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (editorAnchorText(editor.state.doc, 0, middle).length < utf16) low = middle + 1;
      else high = middle;
    }
    appliedAnchor.current = anchor.requestId;
    editor.commands.setTextSelection(Math.max(1, Math.min(low, editor.state.doc.content.size - 1)));
    editor.commands.focus(undefined, { scrollIntoView: false });
    const scroller = editor.view.dom.closest('.main-workspace');
    if (scroller) scroller.scrollTop = anchor.scroll;
  }, [editor, props.restoreAnchor]);
  useEffect(() => {
    if (!editor || !props.writingPreferences?.paragraph_focus) return;
    const root = editor.view.dom;
    const clear = () => { for (const item of Array.from(root.children)) { item.removeAttribute('data-writing-active'); item.removeAttribute('data-writing-inactive'); } };
    const mark = () => {
      if (editor.isDestroyed) return;
      let active = editor.view.domAtPos(editor.state.selection.from).node;
      while (active.parentNode && active.parentNode !== root) active = active.parentNode;
      for (const item of Array.from(root.children)) {
        item.setAttribute('data-writing-active', String(item === active));
        item.setAttribute('data-writing-inactive', String(item !== active));
      }
    };
    mark(); editor.on('selectionUpdate', mark); editor.on('update', mark);
    return () => { editor.off('selectionUpdate', mark); editor.off('update', mark); clear(); };
  }, [editor, props.writingPreferences?.paragraph_focus]);
  useEffect(() => () => clearTimeout(compositionEnd.current), []);
  const preference = props.writingPreferences;
  const style = preference ? {
    '--writing-column-width': { narrow: '48ch', comfortable: '68ch', wide: '88ch' }[preference.column_width],
    '--writing-font-size': `${preference.font_size}px`, '--writing-line-height': preference.line_height,
  } as CSSProperties : undefined;
  return <EditorContent editor={editor} className={`editor${preference ? ' writing-focus-editor' : ''}${preference?.paragraph_focus ? ' writing-paragraph-focus' : ''}`} style={style} />;
}
