// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PromptEditorPanel } from './PromptEditorPanel';
import { newDraft } from './promptDraft';
import { PROMPT_BOUNDS } from './promptTypes';

function props() {
  return { draft: newDraft('editor-usability'), detail: null, mode: 'PROFESSIONAL' as const,
    locked: false, busy: false, canSave: true, conflictCode: null, saveError: null, fieldError: null,
    onEdit: vi.fn(), onSave: vi.fn(), onRetry: vi.fn(), onRebase: vi.fn(), onDiscard: vi.fn() };
}
function description(input: HTMLElement) {
  return (input.getAttribute('aria-describedby') ?? '').split(' ').map(id => document.getElementById(id)?.textContent ?? '').join(' ');
}
afterEach(cleanup);

describe('Prompt editor correction guidance', () => {
  it('counts UTF-8 bytes including Chinese, emoji, newlines and spaces without changing the draft', () => {
    const p = props();
    p.draft.content.text = '中🙂\n A';
    render(<PromptEditorPanel {...p} />);
    const body = screen.getByLabelText('正文') as HTMLTextAreaElement;
    expect(screen.getByText(/正文已用 10 \/ 65536 字节/)).toBeTruthy();
    expect(description(body)).toContain('正文已用 10 / 65536 字节');
    expect(body.value).toBe('中🙂\n A');
    expect(p.onEdit).not.toHaveBeenCalled();
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it('shows exact boundary and excess bytes without clipping input or creating a new save gate', () => {
    const p = props();
    p.draft.content.text = 'x'.repeat(PROMPT_BOUNDS.textBytes);
    const view = render(<PromptEditorPanel {...p} />);
    expect(screen.getByText(/剩余 0 字节/)).toBeTruthy();
    expect(screen.getByLabelText('正文').getAttribute('aria-invalid')).toBe('false');
    const oversized = p.draft.content.text + '🙂';
    view.rerender(<PromptEditorPanel {...p} draft={{ ...p.draft, content: { ...p.draft.content, text: oversized } }} />);
    expect(screen.getByText(/超过上限 4 字节/)).toBeTruthy();
    expect((screen.getByLabelText('正文') as HTMLTextAreaElement).value).toBe(oversized);
    expect(screen.getByLabelText('正文').getAttribute('aria-invalid')).toBe('true');
    expect((screen.getByRole('button', { name: '保存为新 Prompt' }) as HTMLButtonElement).disabled).toBe(false);
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it.each([['text', '正文'], ['seed', 'Seed'], ['parameters', '参数（JSON，不会执行）']])('associates and focuses the existing %s validation error', (field, label) => {
    const p = props();
    const view = render(<PromptEditorPanel {...p} />);
    screen.getByRole('button', { name: '保存为新 Prompt' }).focus();
    view.rerender(<PromptEditorPanel {...p} fieldError={{ field, message: '请修正此字段，原输入已保留' }} />);
    const input = screen.getByLabelText(label);
    expect(document.activeElement).toBe(input);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(description(input)).toContain('请修正此字段，原输入已保留');
    expect(p.onEdit).not.toHaveBeenCalled();
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it('reveals erroneous parameters in novice mode so the user can correct the preserved input', () => {
    const p = props();
    p.draft.content.parameters = '{unfinished';
    const view = render(<PromptEditorPanel {...p} mode="NOVICE" fieldError={{ field: 'parameters', message: '参数不是合法 JSON' }} />);
    const input = screen.getByLabelText('参数（JSON，不会执行）') as HTMLTextAreaElement;
    expect(input.value).toBe('{unfinished');
    expect(document.activeElement).toBe(input);
    expect(screen.getByText(/参数已展开供修正与核对/)).toBeTruthy();
    fireEvent.change(input, { target: { value: '{"steps":2}' } });
    expect(p.onEdit).toHaveBeenCalledWith({ parameters: '{"steps":2}' });
    view.rerender(<PromptEditorPanel {...p} mode="NOVICE" draft={{ ...p.draft, content: { ...p.draft.content, parameters: '{"steps":2}' } }} />);
    expect((screen.getByLabelText('参数（JSON，不会执行）') as HTMLTextAreaElement).value).toBe('{"steps":2}');
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it('does not move focus to a locked field or expose parameters in ordinary novice editing', () => {
    const p = props();
    const view = render(<PromptEditorPanel {...p} mode="NOVICE" />);
    expect(screen.queryByLabelText('参数（JSON，不会执行）')).toBeNull();
    const body = screen.getByLabelText('正文');
    body.focus();
    view.rerender(<PromptEditorPanel {...p} mode="NOVICE" locked fieldError={{ field: 'seed', message: 'Seed 校验失败' }} />);
    expect(document.activeElement).not.toBe(screen.getByLabelText('Seed'));
  });
});
