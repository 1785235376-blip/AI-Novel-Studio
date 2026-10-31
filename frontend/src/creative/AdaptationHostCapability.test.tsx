// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';

const props: CreativeWorkspaceProps = { enabled: true, novelId: 'ordinary-local-project', context: { sessionToken: '', localHostToken: '' },
  scope: { workspace: 'Local', project: 'Ordinary project', storyline: 'Story', branch: 'Main' }, actor: 'Author',
  chapterCount: 0, manuscriptReady: false, novelMain: <div>Original manuscript workspace</div>, novelSidebar: <div />,
  novelInspector: <div />, novelStatus: <span>Local</span>, onExit: vi.fn(), onModuleChange: vi.fn() };
function response(body: unknown) { return { ok: true, status: 200, json: async () => body }; }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('explains missing Host authority without reading private proposals or locking manual Creative editing', async () => {
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith('/capabilities')) return response({ enabled: true, can_mutate: true, modes: ['SCREENPLAY', 'SCRIPT'], source_adaptation: 'HOST_SESSION_REQUIRED' });
    if (url.endsWith('/documents')) return response({ items: [] });
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    throw new Error(`Unexpected private read: ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock); render(<CreativeWorkspace {...props} />);
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  fireEvent.click(within(screen.getByRole('tablist', { name: '创作模式' })).getByRole('tab', { name: /^剧本/ }));
  expect(screen.getByText('来源改编需要已验证的可信 Host 会话。普通手工创作仍可使用。')).toBeTruthy();
  expect(screen.queryByText('访问已锁定')).toBeNull();
  expect((screen.getByLabelText('文档标题') as HTMLInputElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Manual screenplay is preserved' } });
  expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Manual screenplay is preserved');
  expect(fetchMock.mock.calls.some(([url]) => url.includes('/adaptation-proposals'))).toBe(false);
});
