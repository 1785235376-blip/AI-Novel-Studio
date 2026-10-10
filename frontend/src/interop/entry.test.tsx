// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
const { load } = vi.hoisted(() => ({ load: { finish: undefined as undefined | ((value: Record<string, unknown>) => void) } }));
vi.mock('./LocalTutorIntegration', () => new Promise(resolve => { load.finish = resolve; }));
import { useLocalTutorIntegration } from './entry';
const context = { sessionToken: 'synthetic', scope: { workspaceId: 'workspace', projectId: 'project', storylineId: 'story', branchId: 'branch' } };
function Harness() {
  const ui = useLocalTutorIntegration({ context, projectId: 'project', module: 'NOVEL', surface: 'editor', sourceReady: false, onNavigate: vi.fn() });
  return <>{ui.entry}{ui.dialog}<p>当前正文仍保留</p></>;
}
afterEach(cleanup);
it('dismisses a pending deferred load and does not reopen or connect when its module arrives late', async () => {
  const loaded = vi.fn(() => <div role="dialog">Synthetic loaded dialog</div>);
  render(<Harness />); expect(screen.queryByText('正在加载本机 Tutor…')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '问助手' }));
  const cancel = await screen.findByRole('button', { name: '取消加载 Tutor' });
  expect(screen.getByText('当前正文仍保留')).toBeTruthy(); fireEvent.click(cancel);
  await act(async () => { load.finish!({ LocalTutorDialog: loaded }); });
  expect(loaded).not.toHaveBeenCalled(); expect(screen.queryByRole('dialog')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '问助手' }));
  expect(await screen.findByRole('dialog')).toBeTruthy();
});
