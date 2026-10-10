// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { BlankProjectEntry } from './BlankProjectEntry';
afterEach(cleanup);
it('requires a title and sends repeated clicks through one pending creation', async () => {
  let finish!: () => void;
  const create = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  render(<BlankProjectEntry createProject={create} />);
  expect((screen.getByRole('button', { name: '创建空白项目' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('空白项目名称'), { target: { value: '  图片工程  ' } });
  const button = screen.getByRole('button', { name: '创建空白项目' }); fireEvent.click(button); fireEvent.click(button);
  expect(create).toHaveBeenCalledTimes(1); expect(create).toHaveBeenCalledWith('图片工程');
  await act(async () => finish());
});
it('retains the entered title after a creation failure', async () => {
  render(<BlankProjectEntry createProject={vi.fn().mockRejectedValue(new Error('连接未确认，请检查项目列表。'))} />);
  fireEvent.change(screen.getByLabelText('空白项目名称'), { target: { value: '保留名称' } });
  fireEvent.click(screen.getByRole('button', { name: '创建空白项目' }));
  await screen.findByRole('alert');
  expect((screen.getByLabelText('空白项目名称') as HTMLInputElement).value).toBe('保留名称');
});
