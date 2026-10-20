// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PromptEditorPanel } from './PromptEditorPanel';
import { newDraft } from './promptDraft';

afterEach(cleanup);
function props(text = '  第一处🙂 [.]\n第二处🙂  ') {
  const draft = newDraft('draft-a');
  draft.familyId = 'family-a'; draft.baseAssetId = 'asset-a'; draft.baseRevision = 1;
  draft.state = 'DIRTY'; draft.content.text = text;
  return { draft, copyScopeKey: 'project-a:actor-a', detail: null, mode: 'PROFESSIONAL' as const,
    locked: false, busy: false, canSave: true, conflictCode: null, saveError: null, fieldError: null,
    onEdit: vi.fn(), onSave: vi.fn(), onRetry: vi.fn(), onRebase: vi.fn(), onDiscard: vi.fn() };
}
const query = () => screen.getByLabelText('查找当前正文') as HTMLInputElement;
const body = () => screen.getByLabelText('正文') as HTMLTextAreaElement;
const finder = () => within(screen.getByRole('search', { name: '当前正文查找' }));
const action = (name: string) => finder().getByRole('button', { name }) as HTMLButtonElement;
const search = (value: string) => fireEvent.change(query(), { target: { value } });
const selected = () => body().value.slice(body().selectionStart, body().selectionEnd);

it('searches unsaved Unicode text explicitly, cycles both ways and never edits or saves the draft', () => {
  const p = props();
  render(<PromptEditorPanel {...p} />);
  query().focus(); search('🙂');
  expect(document.activeElement).toBe(query());
  expect(finder().getByText('找到 2 处匹配，尚未定位。')).toBeTruthy();
  fireEvent.click(action('下一个匹配'));
  expect(document.activeElement).toBe(body());
  expect(selected()).toBe('🙂');
  expect(body().selectionStart).toBe(body().value.indexOf('🙂'));
  expect(body().selectionEnd - body().selectionStart).toBe(2);
  fireEvent.click(action('下一个匹配'));
  expect(body().selectionStart).toBe(body().value.lastIndexOf('🙂'));
  fireEvent.click(action('下一个匹配'));
  expect(finder().getByText('第 1 / 2 处匹配。')).toBeTruthy();
  fireEvent.click(action('上一个匹配'));
  expect(finder().getByText('第 2 / 2 处匹配。')).toBeTruthy();
  expect(screen.getByText('有未保存修改')).toBeTruthy();
  expect(p.draft.content.text).toBe('  第一处🙂 [.]\n第二处🙂  ');
  for (const callback of [p.onEdit, p.onSave, p.onRetry, p.onRebase, p.onDiscard]) {
    expect(callback).not.toHaveBeenCalled();
  }
});

it('matches literal metacharacters, exact case and spaces, and reports no results honestly', () => {
  const p = props('  a A [.] [.]  ');
  render(<PromptEditorPanel {...p} />);
  for (const [needle, count] of [['[.]', 2], ['a', 1], ['  ', 2]] as const) {
    search(needle);
    expect(finder().getByText(`找到 ${count} 处匹配，尚未定位。`)).toBeTruthy();
    fireEvent.click(action('下一个匹配'));
    expect(selected()).toBe(needle);
  }
  search('absent');
  expect(finder().getByText('当前正文中没有匹配。')).toBeTruthy();
  expect(action('下一个匹配').disabled).toBe(true);
  expect(action('上一个匹配').disabled).toBe(true);
  fireEvent.click(action('清除查找'));
  expect(query().value).toBe('');
  expect(document.activeElement).toBe(query());
  expect(body().value).toBe(p.draft.content.text);
});

it('recounts edited text without keeping a stale result or moving focus', () => {
  const p = props();
  const view = render(<PromptEditorPanel {...p} />);
  search('🙂'); fireEvent.click(action('下一个匹配'));
  const seed = screen.getByLabelText('Seed'); seed.focus();
  const draft = { ...p.draft, content: { ...p.draft.content, text: '更改后的正文🙂' } };
  view.rerender(<PromptEditorPanel {...p} draft={draft} />);
  expect(document.activeElement).toBe(seed);
  expect(query().value).toBe('🙂');
  expect(finder().getByText('找到 1 处匹配，尚未定位。')).toBeTruthy();
  fireEvent.click(action('下一个匹配'));
  expect(selected()).toBe('🙂');
  expect(body().selectionStart).toBe(draft.content.text.indexOf('🙂'));
  expect(p.onEdit).not.toHaveBeenCalled();
  expect(p.onSave).not.toHaveBeenCalled();
});

it.each(['scope', 'key', 'family', 'asset', 'revision'])('clears private search state after %s identity changes with identical body text', identity => {
  const p = props(); const view = render(<PromptEditorPanel {...p} />);
  search('🙂'); fireEvent.click(action('下一个匹配'));
  const originalBody = body();
  const matchEnd = originalBody.selectionEnd;
  const draft = { ...p.draft };
  if (identity === 'key') draft.key = 'draft-b';
  if (identity === 'family') draft.familyId = 'family-b';
  if (identity === 'asset') draft.baseAssetId = 'asset-b';
  if (identity === 'revision') draft.baseRevision = 2;
  view.rerender(<PromptEditorPanel {...p} draft={draft}
    copyScopeKey={identity === 'scope' ? 'project-b:actor-b' : p.copyScopeKey} />);
  expect(query().value).toBe('');
  expect(finder().queryByText(/处匹配/)).toBeNull();
  expect(body()).toBe(originalBody);
  expect([body().selectionStart, body().selectionEnd]).toEqual([matchEnd, matchEnd]);
  expect(body().value).toBe(p.draft.content.text);
  expect(p.onEdit).not.toHaveBeenCalled();
  expect(p.onSave).not.toHaveBeenCalled();
});

it.each(['range', 'caret', 'same-range-user-intent'])(
  'selection ownership: preserves a newer user %s through source retirement and an old callback', kind => {
    const p = props('source 🙂 tail 🙂');
    const view = render(<PromptEditorPanel {...p} />);
    search('🙂'); fireEvent.click(action('下一个匹配'));
    const button = action('下一个匹配');
    const retained = (button as any)[Object.keys(button).find(key => key.startsWith('__reactProps$'))!]
      .onClick as () => void;
    if (kind === 'range') body().setSelectionRange(0, 6);
    if (kind === 'caret') body().setSelectionRange(2, 2);
    if (kind === 'same-range-user-intent') fireEvent.pointerDown(body());
    const userSelection = [body().selectionStart, body().selectionEnd];
    const seed = screen.getByLabelText('Seed'); seed.focus();
    view.rerender(<PromptEditorPanel {...p}
      draft={{ ...p.draft, familyId: 'family-b', baseAssetId: 'asset-b', baseRevision: 2 }} />);
    expect([body().selectionStart, body().selectionEnd]).toEqual(userSelection);
    expect(document.activeElement).toBe(seed);
    retained();
    expect([body().selectionStart, body().selectionEnd]).toEqual(userSelection);
    expect(document.activeElement).toBe(seed);
    expect(body().value).toBe(p.draft.content.text);
    for (const callback of [p.onEdit, p.onSave, p.onRetry, p.onRebase, p.onDiscard]) {
      expect(callback).not.toHaveBeenCalled();
    }
  });

it('selection ownership: ordinary query edits and clearing preserve the native range until its source retires', () => {
  const p = props(); const view = render(<PromptEditorPanel {...p} />);
  search('🙂'); fireEvent.click(action('下一个匹配'));
  const match = [body().selectionStart, body().selectionEnd];
  query().focus(); search('[.]');
  expect([body().selectionStart, body().selectionEnd]).toEqual(match);
  fireEvent.click(action('清除查找'));
  expect([body().selectionStart, body().selectionEnd]).toEqual(match);
  const seed = screen.getByLabelText('Seed'); seed.focus();
  view.rerender(<PromptEditorPanel {...p} draft={{ ...p.draft, baseRevision: 2 }} />);
  expect([body().selectionStart, body().selectionEnd]).toEqual([match[1], match[1]]);
  expect(document.activeElement).toBe(seed);
  expect(p.onEdit).not.toHaveBeenCalled(); expect(p.onSave).not.toHaveBeenCalled();
});

it('uses Enter and Shift+Enter only after search-field IME composition has finished', () => {
  const p = props(); render(<PromptEditorPanel {...p} />);
  query().focus(); search('🙂'); body().setSelectionRange(1, 1);
  fireEvent.compositionStart(query());
  expect(action('下一个匹配').disabled).toBe(true);
  fireEvent.keyDown(query(), { key: 'Enter', keyCode: 229, isComposing: true });
  expect(body().selectionStart).toBe(1);
  expect(document.activeElement).toBe(query());
  fireEvent.compositionEnd(query());
  fireEvent.keyDown(query(), { key: 'Enter', keyCode: 229 });
  expect(body().selectionStart).toBe(1);
  fireEvent.keyDown(query(), { key: 'Enter' });
  expect(finder().getByText('第 1 / 2 处匹配。')).toBeTruthy();
  fireEvent.keyDown(query(), { key: 'Enter', shiftKey: true });
  expect(finder().getByText('第 2 / 2 处匹配。')).toBeTruthy();
  expect(p.onEdit).not.toHaveBeenCalled(); expect(p.onSave).not.toHaveBeenCalled();
});

it('does not steal body IME focus or selection while composition is active', () => {
  const p = props(); render(<PromptEditorPanel {...p} />);
  search('🙂'); body().focus(); body().setSelectionRange(1, 1);
  fireEvent.compositionStart(body());
  expect(query().disabled).toBe(true);
  expect(action('下一个匹配').disabled).toBe(true);
  fireEvent.click(action('下一个匹配'));
  expect(document.activeElement).toBe(body()); expect(body().selectionStart).toBe(1);
  fireEvent.compositionEnd(body());
  fireEvent.click(action('下一个匹配'));
  expect(selected()).toBe('🙂');
  expect(p.onEdit).not.toHaveBeenCalled(); expect(p.onSave).not.toHaveBeenCalled();
});

it.each(['locked', 'busy'] as const)('blocks selection navigation when the editor becomes %s', flag => {
  const p = props(); const view = render(<PromptEditorPanel {...p} />);
  search('🙂'); body().setSelectionRange(1, 1);
  view.rerender(<PromptEditorPanel {...p} {...{ [flag]: true }} />);
  expect(query().disabled).toBe(true);
  expect(action('下一个匹配').disabled).toBe(true);
  fireEvent.click(action('下一个匹配'));
  expect(body().selectionStart).toBe(1);
  expect(p.onSave).not.toHaveBeenCalled();
});

it('uses native textarea offsets for CRLF and bare CR without normalizing the owner draft', () => {
  const original = '  首行\r\n第二行🙂\r尾行🙂  ';
  const p = props(original); render(<PromptEditorPanel {...p} />);
  search('🙂'); fireEvent.click(action('下一个匹配'));
  expect(selected()).toBe('🙂');
  expect(body().selectionStart).toBe(body().value.indexOf('🙂'));
  fireEvent.click(action('下一个匹配'));
  expect(body().selectionStart).toBe(body().value.lastIndexOf('🙂'));
  expect(p.draft.content.text).toBe(original);
  expect(p.onEdit).not.toHaveBeenCalled();
});

it('counts a 64 KiB emoji body without rendering one node per match', () => {
  const p = props('🙂'.repeat(16384)); render(<PromptEditorPanel {...p} />);
  search('🙂');
  expect(finder().getByText('找到 16384 处匹配，尚未定位。')).toBeTruthy();
  fireEvent.click(action('上一个匹配'));
  expect(body().selectionStart).toBe(body().value.length - 2);
  expect(selected()).toBe('🙂');
  expect(finder().getAllByRole('button')).toHaveLength(3);
  expect(p.onEdit).not.toHaveBeenCalled(); expect(p.onSave).not.toHaveBeenCalled();
});
