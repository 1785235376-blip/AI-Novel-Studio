// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PromptEditorPanel } from './PromptEditorPanel';
import { newDraft } from './promptDraft';

const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
const writeText = vi.fn<(text: string) => Promise<void>>();
function clipboard(value: unknown) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value });
}
function props() {
  const draft = newDraft('family-a');
  draft.content.text = '  中文🙂\ttext\r\nsecond line\n\n';
  draft.state = 'DIRTY';
  return { draft, copyScopeKey: 'project-a', detail: null, mode: 'PROFESSIONAL' as const,
    locked: false, busy: false, canSave: true, conflictCode: null, saveError: null, fieldError: null,
    onEdit: vi.fn(), onSave: vi.fn(), onRetry: vi.fn(), onRebase: vi.fn(), onDiscard: vi.fn() };
}
function pending() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const copyButton = () => screen.getByRole('button', { name: '复制当前正文' });
const copied = () => screen.queryByText(/当前正文已复制到剪贴板/);
beforeEach(() => { writeText.mockReset().mockResolvedValue(); clipboard({ writeText }); });
afterEach(() => {
  cleanup();
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard);
  else Reflect.deleteProperty(navigator, 'clipboard');
});

describe('explicit visible Prompt body copy', () => {
  it('writes the exact current draft only after a click and does not save or edit', async () => {
    const p = props();
    render(<PromptEditorPanel {...p} />);
    expect(writeText).not.toHaveBeenCalled();
    expect(copied()).toBeNull();
    fireEvent.click(copyButton());
    await screen.findByText(/当前正文已复制到剪贴板/);
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(p.draft.content.text);
    expect(screen.getByText(/不包含其他参数，也不代表已保存/)).toBeTruthy();
    expect(p.onSave).not.toHaveBeenCalled();
    expect(p.onEdit).not.toHaveBeenCalled();
    expect(p.onDiscard).not.toHaveBeenCalled();
    expect(screen.getByText('有未保存修改')).toBeTruthy();
  });

  it('waits for the clipboard receipt and prevents duplicate in-flight attempts', async () => {
    const request = pending();
    writeText.mockReturnValue(request.promise);
    render(<PromptEditorPanel {...props()} />);
    fireEvent.click(copyButton());
    const busy = screen.getByRole('button', { name: '正在复制正文…' });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(busy);
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(copied()).toBeNull();
    await act(async () => request.resolve());
    expect(copied()).toBeTruthy();
  });

  it.each(['unavailable', 'rejected', 'throws'])('offers explicit manual selection when clipboard is %s', async kind => {
    if (kind === 'unavailable') clipboard(undefined);
    if (kind === 'rejected') writeText.mockRejectedValue(new Error('synthetic permission denial'));
    if (kind === 'throws') writeText.mockImplementation(() => { throw new Error('synthetic clipboard exception'); });
    const p = props();
    render(<PromptEditorPanel {...p} />);
    fireEvent.click(copyButton());
    await screen.findByText(/无法自动复制/);
    const attempts = writeText.mock.calls.length;
    const body = screen.getByLabelText('正文') as HTMLTextAreaElement;
    expect(document.activeElement).not.toBe(body);
    fireEvent.click(screen.getByRole('button', { name: '选中正文手动复制' }));
    expect(document.activeElement).toBe(body);
    expect(body.selectionStart).toBe(0);
    expect(body.selectionEnd).toBe(body.value.length);
    expect(screen.getByText(/Ctrl\+C 或 Command\+C/)).toBeTruthy();
    expect(writeText).toHaveBeenCalledTimes(attempts);
    expect(copied()).toBeNull();
    expect(p.onEdit).not.toHaveBeenCalled();
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it.each(['draft', 'project'])('does not attach a late clipboard success to another %s', async change => {
    const request = pending();
    writeText.mockReturnValue(request.promise);
    const p = props();
    const view = render(<PromptEditorPanel {...p} />);
    fireEvent.click(copyButton());
    const next = change === 'draft' ? { ...p, draft: { ...p.draft, key: 'family-b' } }
      : { ...p, copyScopeKey: 'project-b' };
    view.rerender(<PromptEditorPanel {...next} />);
    expect(screen.getByText(/先前正文的复制请求仍在处理中/)).toBeTruthy();
    await act(async () => request.resolve());
    expect(copied()).toBeNull();
    expect((copyButton() as HTMLButtonElement).disabled).toBe(false);
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it('invalidates a pending receipt even if text changes away and back', async () => {
    const request = pending();
    writeText.mockReturnValue(request.promise);
    const p = props();
    const view = render(<PromptEditorPanel {...p} />);
    fireEvent.click(copyButton());
    view.rerender(<PromptEditorPanel {...p} draft={{ ...p.draft, content: { ...p.draft.content, text: 'changed' } }} />);
    view.rerender(<PromptEditorPanel {...p} />);
    await act(async () => request.reject(new Error('late denial')));
    expect(copied()).toBeNull();
    expect(screen.queryByText(/无法自动复制/)).toBeNull();
    expect(document.activeElement).not.toBe(screen.getByLabelText('正文'));
  });

  it('clears old success after editing and allows a new explicit attempt', async () => {
    const p = props();
    const view = render(<PromptEditorPanel {...p} />);
    fireEvent.click(copyButton());
    await screen.findByText(/当前正文已复制到剪贴板/);
    view.rerender(<PromptEditorPanel {...p} draft={{ ...p.draft, content: { ...p.draft.content, text: '\n new body ' } }} />);
    expect(copied()).toBeNull();
    fireEvent.click(copyButton());
    await screen.findByText(/当前正文已复制到剪贴板/);
    expect(writeText).toHaveBeenLastCalledWith('\n new body ');
  });

  it('does not show late feedback after unmounting and reopening the editor', async () => {
    const request = pending();
    writeText.mockReturnValue(request.promise);
    const view = render(<PromptEditorPanel {...props()} />);
    fireEvent.click(copyButton());
    view.unmount();
    render(<PromptEditorPanel {...props()} copyScopeKey="project-b" />);
    await act(async () => request.resolve());
    expect(copied()).toBeNull();
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it('allows a second explicit copy after reopening without attributing the old receipt to it', async () => {
    const first = pending();
    writeText.mockReturnValueOnce(first.promise).mockResolvedValueOnce();
    const p = props();
    const view = render(<PromptEditorPanel {...p} />);
    fireEvent.click(copyButton());
    view.unmount();
    render(<PromptEditorPanel {...p} copyScopeKey="project-b"
      draft={{ ...p.draft, content: { ...p.draft.content, text: 'new body' } }} />);
    fireEvent.click(copyButton());
    await screen.findByText(/当前正文已复制到剪贴板/);
    expect(writeText.mock.calls.map(([text]) => text)).toEqual([p.draft.content.text, 'new body']);
    await act(async () => first.reject(new Error('old request failed after reopening')));
    expect(copied()).toBeTruthy();
    expect(screen.queryByText(/无法自动复制/)).toBeNull();
    expect((screen.getByLabelText('正文') as HTMLTextAreaElement).value).toBe('new body');
    // This checks UI attribution, not actual browser clipboard completion ordering.
  });

  it.each(['empty', 'locked'])('does not copy a %s editor', condition => {
    const p = props();
    if (condition === 'empty') p.draft.content.text = '';
    render(<PromptEditorPanel {...p} locked={condition === 'locked'} />);
    expect((copyButton() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(copyButton());
    expect(writeText).not.toHaveBeenCalled();
  });
});
