// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ChapterTree, CreateChapterDialog } from './ChapterTree';

afterEach(cleanup);
function tree(onCreate: (title: string) => Promise<void> | void = vi.fn()) {
  render(<StrictMode><ChapterTree chapters={[]} onSelect={vi.fn()} onCreate={onCreate} /></StrictMode>);
  const trigger = screen.getByRole('button', { name: '新建章节' });
  trigger.focus(); fireEvent.click(trigger);
  return { trigger, input: screen.getByLabelText('章节标题'), onCreate };
}
it('focuses title, contains forward/backward Tab and restores the trigger on Escape', () => {
  const { trigger, input } = tree();
  const create = screen.getByRole('button', { name: '创建章节' });
  expect(document.activeElement).toBe(input);
  fireEvent.keyDown(input, { key: 'Tab', shiftKey: true });
  expect(document.activeElement).toBe(create);
  fireEvent.keyDown(create, { key: 'Tab' });
  expect(document.activeElement).toBe(input);
  fireEvent.keyDown(input, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(document.activeElement).toBe(trigger);
});
it('keeps title and dialog open for IME Escape/Enter, then allows an explicit close', () => {
  const { input, onCreate } = tree();
  fireEvent.change(input, { target: { value: '中文候选' } });
  fireEvent.compositionStart(input);
  fireEvent.keyDown(input, { key: 'Escape', isComposing: true });
  fireEvent.submit(input.closest('form')!);
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(onCreate).not.toHaveBeenCalled();
  expect((input as HTMLInputElement).value).toBe('中文候选');
  fireEvent.compositionEnd(input);
  fireEvent.keyDown(input, { key: 'Escape', keyCode: 229 });
  expect(screen.getByRole('dialog')).toBeTruthy();
  fireEvent.keyDown(input, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).toBeNull();
});
it('locks one pending create, prevents Escape cancellation and restores focus after success', async () => {
  let finish!: () => void;
  const onCreate = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  const { input, trigger } = tree(onCreate);
  fireEvent.change(input, { target: { value: '  第二章  ' } });
  const form = input.closest('form')!;
  fireEvent.submit(form); fireEvent.submit(form);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(onCreate).toHaveBeenCalledTimes(1);
  expect(onCreate).toHaveBeenCalledWith('第二章');
  expect((input as HTMLInputElement).disabled).toBe(true);
  await act(async () => finish());
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(document.activeElement).toBe(trigger);
});
it('rerenders pending state without clearing typed input or accumulating listeners', () => {
  const close = vi.fn(), submit = vi.fn();
  const view = render(<CreateChapterDialog open onSubmit={submit} onClose={close} />);
  const input = screen.getByLabelText('章节标题');
  fireEvent.change(input, { target: { value: '保留标题' } });
  view.rerender(<CreateChapterDialog open pending onSubmit={submit} onClose={() => close()} />);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(close).not.toHaveBeenCalled();
  expect((input as HTMLInputElement).value).toBe('保留标题');
  view.rerender(<CreateChapterDialog open onSubmit={submit} onClose={() => close()} />);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(close).toHaveBeenCalledTimes(1);
  view.unmount(); fireEvent.keyDown(document, { key: 'Escape' });
  expect(close).toHaveBeenCalledTimes(1);
});
it('cancel restores focus without a write and a new opening starts empty', () => {
  const { input, trigger, onCreate } = tree();
  fireEvent.change(input, { target: { value: '仅临时标题' } });
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(document.activeElement).toBe(trigger); expect(onCreate).not.toHaveBeenCalled();
  fireEvent.click(trigger);
  expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('');
});
