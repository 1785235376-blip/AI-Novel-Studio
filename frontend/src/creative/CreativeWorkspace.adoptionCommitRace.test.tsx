// @vitest-environment jsdom
// Exercise the real host state at its original owner callbacks, without changing frozen tests.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StoryboardWorkspacePanelProps } from '../storyboard/StoryboardWorkspacePanel';
import type { CreativeDocument } from './types';
import { newDocument, newScene, newShot } from './types';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';

const captured = vi.hoisted(() => ({
  storyboard: undefined as StoryboardWorkspacePanelProps | undefined,
  production: undefined as { onDocument: (document: CreativeDocument) => void } | undefined,
}));
vi.mock('../storyboard/StoryboardWorkspacePanel', () => ({
  StoryboardWorkspacePanel: (props: StoryboardWorkspacePanelProps) => { captured.storyboard = props; return null; },
}));
vi.mock('./StoryboardProductionPanel', () => ({
  StoryboardProductionPanel: (props: { onDocument: (document: CreativeDocument) => void }) => {
    captured.production = props; return null;
  },
}));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); captured.storyboard = undefined; captured.production = undefined; });

const document = (version: number, text: string): CreativeDocument => ({
  ...newDocument('STORYBOARD'), id: 'doc-1', version, title: `Board v${version}`, status: 'DRAFT',
  source_independent: true, actor_id: 'actor-1', created_at: '2026-10-17T00:00:00Z', updated_at: '2026-10-17T00:00:00Z',
  source_evidence: {}, scenes: [{ ...newScene(1), id: 'scene-1' }],
  shots: [{ ...newShot(1, 'scene-1'), id: 'shot-1', frame_prompt: text }],
});
async function mountHost() {
  const original = document(2, 'original target');
  const response = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
  const fetch = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url.endsWith('/capabilities')) return response({ enabled: true, can_mutate: true,
      modes: ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD', 'PRODUCTION'] });
    if (url.endsWith('/documents') && init.method === 'GET') return response({ items: [original] });
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    if (url.endsWith('/director-proposals') || url.endsWith('/model-routes')) return response({ items: [] });
    return { ok: false, status: 404, json: async () => ({ code: 'UNAVAILABLE' }) };
  });
  vi.stubGlobal('fetch', fetch);
  const props: CreativeWorkspaceProps = { enabled: true, novelId: 'p1',
    context: { sessionToken: 'session-1', actor: { id: 'actor-1', displayName: 'Author', workspaceId: 'w' } },
    scope: { workspace: 'Workspace', project: 'Project', storyline: 'Story', branch: 'Main' }, actor: 'Author',
    chapterCount: 0, manuscriptReady: false, novelMain: null, novelSidebar: null, novelInspector: null,
    novelStatus: null, onExit: vi.fn(), onModuleChange: vi.fn() };
  render(<CreativeWorkspace {...props} />);
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  fireEvent.click(within(screen.getByRole('tablist', { name: '创作模式' })).getByRole('tab', { name: /Storyboard/ }));
  await screen.findByText('已保存 · v2');
  fireEvent.click(screen.getByRole('button', { name: '按需打开镜头工作区' }));
  await waitFor(() => expect(captured.storyboard?.onDocumentCommitted).toBeTruthy());
  // Save the callback before any other owner updates the host, matching a delayed readback.
  const deliver = captured.storyboard!.onDocumentCommitted as unknown as
    (document: CreativeDocument, expectedTargetVersion: number) => void;
  return { deliver, fetch };
}

describe('CreativeWorkspace adoption readback admission', () => {
  it('accepts a verified adoption only against the still-current original target version', async () => {
    const h = await mountHost();
    act(() => h.deliver(document(3, 'adopted prompt'), 2));
    expect(screen.getByText('已保存 · v3')).toBeTruthy();
    expect((screen.getByLabelText('画面描述') as HTMLTextAreaElement).value).toBe('adopted prompt');
    expect(h.fetch.mock.calls.some(([, init]) => init?.method && init.method !== 'GET')).toBe(false);
  });
  it('a late adoption v3 cannot replace a clean v4 already accepted from the original production owner', async () => {
    const h = await mountHost();
    act(() => captured.production!.onDocument(document(4, 'newer owner result')));
    expect(screen.getByText('已保存 · v4')).toBeTruthy();
    expect(() => h.deliver(document(3, 'late adopted prompt'), 2)).toThrow();
    expect(screen.getByText('已保存 · v4')).toBeTruthy();
    expect((screen.getByLabelText('画面描述') as HTMLTextAreaElement).value).toBe('newer owner result');
    expect(screen.queryByText(/已回读确认 Prompt 采用/)).toBeNull();
  });
});
