/** Local, literal search of the current textarea, including unsaved edits. */
import { useEffect, useId, useMemo, useRef, useState, type RefObject } from 'react';
import { Button } from '../ui/primitives';

export function PromptBodyFinder({ text, target, disabled }: {
  text: string; target: RefObject<HTMLTextAreaElement>; disabled: boolean;
}) {
  const queryId = useId();
  const hintId = useId();
  const queryInput = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [composing, setComposing] = useState(false);
  const composingRef = useRef(false);
  const alive = useRef(true);
  const ownedSelection = useRef<{
    input: HTMLTextAreaElement; value: string; start: number; end: number; direction: string;
  } | null>(null);
  const current = useRef({ text, query, disabled });
  current.current = { text, query, disabled };
  const [active, setActive] = useState<{ text: string; query: string; index: number } | null>(null);
  // Textarea selection offsets address its newline-normalized DOM value. Never
  // normalize the owner's draft or write the displayed value back to it.
  const visibleText = useMemo(() => text.replace(/\r\n?/g, '\n'), [text]);
  const matches = useMemo(() => {
    const positions: number[] = [];
    if (query) {
      for (let offset = visibleText.indexOf(query); offset >= 0;
        offset = visibleText.indexOf(query, offset + query.length)) positions.push(offset);
    }
    return positions;
  }, [visibleText, query]);
  const activeIndex = active?.text === text && active.query === query ? active.index : -1;
  useEffect(() => { setActive(null); }, [text, query]);
  useEffect(() => {
    alive.current = true;
    const input = target.current;
    const release = () => { ownedSelection.current = null; };
    const unchanged = () => {
      const held = ownedSelection.current;
      return held && input && held.input === input && input.value === held.value
        && input.selectionStart === held.start && input.selectionEnd === held.end
        && input.selectionDirection === held.direction;
    };
    const releaseMovedSelection = () => { if (!unchanged()) release(); };
    // Manual interaction owns the selection even if its final offsets happen to
    // equal the last match. Native select events from our own navigation may be
    // queued, so only a changed native range releases ownership on that event.
    const interactions = ['pointerdown', 'keydown', 'beforeinput', 'input', 'compositionstart'];
    interactions.forEach(event => input?.addEventListener(event, release));
    input?.addEventListener('select', releaseMovedSelection);
    return () => {
      alive.current = false;
      interactions.forEach(event => input?.removeEventListener(event, release));
      input?.removeEventListener('select', releaseMovedSelection);
      // A keyed source change remounts the finder but can reuse the textarea.
      // Retire only our untouched range; never focus or rewrite the draft.
      if (input && target.current === input && unchanged()) {
        input.setSelectionRange(input.selectionEnd, input.selectionEnd);
      }
      release();
    };
  }, [target]);

  const locate = (direction: 1 | -1) => {
    const input = target.current;
    if (!alive.current || current.current.disabled || composingRef.current || !matches.length
      || current.current.text !== text || current.current.query !== query
      || !input || input.disabled || input.value !== visibleText) return;
    const index = activeIndex < 0 ? (direction === 1 ? 0 : matches.length - 1)
      : (activeIndex + direction + matches.length) % matches.length;
    input.focus();
    input.setSelectionRange(matches[index], matches[index] + query.length);
    ownedSelection.current = { input, value: input.value, start: input.selectionStart,
      end: input.selectionEnd, direction: input.selectionDirection };
    setActive({ text, query, index });
  };

  return <div role="search" aria-label="当前正文查找">
    <label htmlFor={queryId}>查找当前正文</label>
    <input ref={queryInput} id={queryId} type="search" value={query} disabled={disabled}
      aria-describedby={hintId} aria-controls="prompt-text"
      onChange={event => setQuery(event.target.value)}
      onCompositionStart={() => { composingRef.current = true; setComposing(true); }}
      onCompositionEnd={() => { composingRef.current = false; setComposing(false); }}
      onKeyDown={event => {
        if (event.key !== 'Enter' || composingRef.current || event.nativeEvent.isComposing
          || event.nativeEvent.keyCode === 229) return;
        event.preventDefault();
        locate(event.shiftKey ? -1 : 1);
      }} />
    <p id={hintId} className="prompt-diff-limit">
      仅查找当前编辑框（含未保存修改），按字面区分大小写、保留查找空格，匹配互不重叠。
      Enter 查找下一个，Shift+Enter 查找上一个，循环定位。
    </p>
    <div className="prompt-editor-actions">
      <Button type="button" disabled={disabled || composing || !matches.length}
        onClick={() => locate(-1)}>上一个匹配</Button>
      <Button type="button" disabled={disabled || composing || !matches.length}
        onClick={() => locate(1)}>下一个匹配</Button>
      <Button type="button" variant="ghost" disabled={disabled || composing || !query}
        onClick={() => { setQuery(''); setActive(null); queryInput.current?.focus(); }}>清除查找</Button>
      <span role="status" aria-live="polite">{!query ? '输入文字查找当前正文。'
        : !matches.length ? '当前正文中没有匹配。'
        : activeIndex < 0 ? `找到 ${matches.length} 处匹配，尚未定位。`
        : `第 ${activeIndex + 1} / ${matches.length} 处匹配。`}</span>
    </div>
  </div>;
}
