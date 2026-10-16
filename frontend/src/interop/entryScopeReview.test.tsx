// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

const { deferred } = vi.hoisted(() => ({ deferred: {
  started: false,
  finish: undefined as undefined | ((value: Record<string, unknown>) => void),
} }));
vi.mock('./LocalTutorIntegration', () => {
  deferred.started = true;
  return new Promise(resolve => { deferred.finish = resolve; });
});
import { useLocalTutorIntegration } from './entry';

function Harness({ projectId }: { projectId: string }) {
  const ui = useLocalTutorIntegration({
    context: { sessionToken: 'synthetic', scope: { workspaceId: 'workspace', projectId, storylineId: 'story', branchId: 'branch' } },
    projectId, module: 'NOVEL', surface: 'editor', sourceReady: false, onNavigate: vi.fn(),
  });
  return <>{ui.entry}{ui.settings}{ui.dialog}<p>Project: {projectId}</p></>;
}

afterEach(cleanup);

it('does not import the dialog initially and discards its pending load across a project switch', async () => {
  const loaded = vi.fn(() => <div role="dialog">Loaded old project dialog</div>);
  const view = render(<Harness projectId="project-a" />);
  expect(deferred.started).toBe(false);
  expect(screen.queryByRole('dialog')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '本机 Tutor 集成设置' }));
  await waitFor(() => expect(deferred.started).toBe(true));
  expect(screen.getByRole('button', { name: '取消加载 Tutor' })).toBeTruthy();
  view.rerender(<Harness projectId="project-b" />);
  await act(async () => deferred.finish!({ LocalTutorDialog: loaded }));
  expect(loaded).not.toHaveBeenCalled();
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(screen.queryByRole('button', { name: '取消加载 Tutor' })).toBeNull();
  expect(screen.getByText('Project: project-b')).toBeTruthy();
});
