// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { fixtureProjection } from '../director/directorWorkspaceFixtures.testFixture';
import type { DirectorWorkspaceProjection } from '../director/directorWorkspaceTypes';
import { StudioGraphDirectorConsole } from './StudioGraphDirectorConsole';

const snapshot = { id: 'doc-1', version: 3, digest: 'a'.repeat(64) };
const projection = () => {
  const value = fixtureProjection(); value.document.mode = 'DIRECTOR'; return value;
};
const execute = <T,>(work: () => Promise<T>) => work();
const expand = () => fireEvent.click(screen.getByRole('button', { name: '展开导演控制台并核对来源' }));
function setup(patch: Partial<ComponentProps<typeof StudioGraphDirectorConsole>> = {}) {
  const client = { readDirectorWorkspace: vi.fn().mockResolvedValue(projection()) };
  const props: ComponentProps<typeof StudioGraphDirectorConsole> = { client, nodeId: 'director-one', snapshot,
    identity: 'actor-project-scope', active: true, referenceState: 'CURRENT', isCurrent: () => true, read: execute, ...patch };
  const view = render(<StudioGraphDirectorConsole {...props} />);
  return { client, ...view, rerender: (next: Partial<typeof props>) => view.rerender(<StudioGraphDirectorConsole {...props} {...next} />) };
}
afterEach(cleanup);

describe('Director Console is opened from its existing graph participant', () => {
  it('waits for explicit expansion and renders the existing seven-dimension workspace through the parent read guard', async () => {
    const read = vi.fn(), { client } = setup({ read: <T,>(work: () => Promise<T>) => { read(); return work(); } });
    expect(client.readDirectorWorkspace).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('导演意图')).toBeNull();
    expand();
    const intent = await screen.findByLabelText('导演意图');
    expect(intent.querySelectorAll('[data-field]').length).toBe(7);
    expect(client.readDirectorWorkspace).toHaveBeenCalledWith(snapshot, expect.any(AbortSignal));
    expect(read).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: '收起导演控制台' }).getAttribute('aria-expanded')).toBe('true');
    expect(screen.queryByRole('button', { name: /提交|应用|派发|生成|保存/ })).toBeNull();
  });

  it('collapsing aborts a pending read and drops the existing workspace local camera draft', async () => {
    const { client } = setup(); expand(); await screen.findByLabelText('导演意图');
    const camera = screen.getAllByRole('combobox', { name: '摄影机运动' })[0];
    fireEvent.change(camera, { target: { value: 'DOLLY' } });
    expect(screen.getByText(/本地镜头语言草稿 1 项/)).toBeTruthy();
    const signal = client.readDirectorWorkspace.mock.calls[0][1] as AbortSignal;
    fireEvent.click(screen.getByRole('button', { name: '收起导演控制台' }));
    expect(signal.aborted).toBe(true); expect(screen.queryByLabelText('导演意图')).toBeNull();
    expand(); await screen.findByLabelText('导演意图');
    expect(screen.queryByText(/本地镜头语言草稿 1 项/)).toBeNull();
  });

  it.each(['nodeId', 'identity', 'snapshot'] as const)('clears private output immediately after %s changes', async field => {
    const { rerender } = setup(); expand(); await screen.findByLabelText('导演意图');
    rerender(field === 'snapshot' ? { snapshot: { ...snapshot, version: 4 } } : { [field]: 'another' });
    expect(screen.queryByLabelText('导演意图')).toBeNull();
    expect(screen.getByRole('button', { name: '展开导演控制台并核对来源' })).toBeTruthy();
  });

  it.each(['STALE', 'UNAVAILABLE'] as const)('hides private output and never reads after reference becomes %s', async referenceState => {
    const { client, rerender } = setup(); expand(); await screen.findByLabelText('导演意图');
    rerender({ referenceState });
    expect(screen.queryByLabelText('导演意图')).toBeNull();
    expect(screen.queryByRole('button', { name: /展开导演控制台/ })).toBeNull();
    expect(client.readDirectorWorkspace).toHaveBeenCalledOnce();
  });

  it('does not reveal a late successful result after parent authority retirement', async () => {
    let resolve!: (value: DirectorWorkspaceProjection) => void, current = true;
    const promise = new Promise<DirectorWorkspaceProjection>(yes => { resolve = yes; });
    const { client } = setup({ isCurrent: () => current }); client.readDirectorWorkspace.mockReturnValue(promise);
    expand(); await waitFor(() => expect(client.readDirectorWorkspace).toHaveBeenCalledOnce());
    current = false; await act(async () => resolve(projection()));
    expect(screen.queryByLabelText('导演意图')).toBeNull();
    await screen.findByText(/STUDIO_GRAPH_SCOPE_MISMATCH/);
  });

  it('clears existing output on a revoked refresh and preserves the exact owner error', async () => {
    const { client } = setup(); expand(); await screen.findByLabelText('导演意图');
    client.readDirectorWorkspace.mockRejectedValueOnce(new ApiError({ status: 403, code: 'PROJECT_SCOPE_FORBIDDEN', message: 'Denied by owner.' }));
    fireEvent.click(screen.getByRole('button', { name: '重新读取原文档' }));
    await screen.findByText(/PROJECT_SCOPE_FORBIDDEN/);
    expect(screen.queryByLabelText('导演意图')).toBeNull();
  });

  it('refuses a newer document from an injected reader rather than silently adopting it', async () => {
    const { client } = setup(), changed = projection(); changed.document.version++;
    client.readDirectorWorkspace.mockResolvedValueOnce(changed); expand();
    await screen.findByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/);
    expect(screen.queryByLabelText('导演意图')).toBeNull();
  });

  it('does not request while inactive, missing a source pin, or lacking the original reader', () => {
    const { client, rerender } = setup({ active: false });
    expect(screen.queryByRole('button')).toBeNull();
    rerender({ active: true, snapshot: undefined }); expect(screen.queryByRole('button')).toBeNull();
    rerender({ active: true, client: {} }); expect(screen.getByText(/未连接导演控制台读取通道/)).toBeTruthy();
    expect(client.readDirectorWorkspace).not.toHaveBeenCalled();
  });
});
