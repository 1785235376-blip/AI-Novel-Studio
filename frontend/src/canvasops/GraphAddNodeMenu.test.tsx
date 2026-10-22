/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { modelCatalog } from '../creative/studioGraphModel.testFixtures';
import { blankGraph } from '../creative/graphDraft';
import { GraphAddNodeMenu } from './GraphAddNodeMenu';

afterEach(() => cleanup());

it('opens minimal add menu with creation filter and picks a type', () => {
  const onPick = vi.fn();
  const onCancel = vi.fn();
  render(<GraphAddNodeMenu open catalog={modelCatalog()} definition={blankGraph()} editable
    role="creation" onPick={onPick} onCancel={onCancel} anchor={{ left: 12, top: 20 }} />);
  const dialog = screen.getByRole('dialog', { name: '加节点最小菜单' });
  expect(dialog.getAttribute('data-canvas-role')).toBe('creation');
  expect(dialog.textContent).toContain('拖入素材');
  expect(dialog.textContent).toContain('引用');
  const search = screen.getByRole('searchbox', { name: '搜索加节点类型' });
  fireEvent.change(search, { target: { value: 'text_input' } });
  fireEvent.click(screen.getByRole('button', { name: /text_input/ }));
  expect(onPick).toHaveBeenCalledWith('text_input');
  fireEvent.keyDown(dialog, { key: 'Escape' });
  expect(onCancel).toHaveBeenCalled();
});
