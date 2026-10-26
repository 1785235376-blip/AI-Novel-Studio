// @vitest-environment jsdom
// Consumes a captured original File/API protocol fixture. HTTP replay is in
// process; the synthetic owner states prove neither generation nor acceptance.
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {useLayoutEffect} from 'react';
import fixture from '../../creative/fixtures/cloud-canvas-candidate.file-api.json';
import {setCollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {captureCanvasTaskOwner, readCanvasTaskBinding, writeCanvasTaskBinding} from './canvasTaskBinding';
import {CanvasNodeTaskStatus} from './CanvasNodeTaskStatus';
import {checkedCanvasTaskCandidate} from './canvasTaskCandidate';
import {CanvasTaskCandidateView} from './CanvasTaskCandidateView';

const NativeURL = URL, nodeId = 'file-protocol-node';
const createUrl = vi.fn((_blob: Blob) => 'blob:captured-file-protocol'), revokeUrl = vi.fn();
beforeEach(() => {
  localStorage.clear(); useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''});
  bindLocalHostSession('synthetic-browser-host', {session_mode: 'LOCAL_HOST', actor_id: 'synthetic-browser-author'});
  createUrl.mockClear(); revokeUrl.mockClear();
  vi.stubGlobal('URL', class extends NativeURL {static createObjectURL = createUrl; static revokeObjectURL = revokeUrl;});
  localStorage.setItem(canvasStorageKey('image', fixture.project_id), JSON.stringify({nodes: [{
    id: nodeId, t: 'image_generate', title: 'Synthetic File protocol node', x: 0, y: 0,
    prompt: fixture.pending_inline.items[0].prompt,
  }], edges: []}));
  const owner = captureCanvasTaskOwner(fixture.project_id);
  if (!owner || !writeCanvasTaskBinding(owner, nodeId, fixture.task_id)) throw new Error('Synthetic browser binding unavailable');
});

afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

it.each(['pending_inline', 'approved'] as const)('uses original File/API %s fields without inventing candidate or version fields', async mode => {
  expect(fixture.fixture_kind).toBe('EXPLICIT_SYNTHETIC_OWNER_STATES_NO_EXECUTION_OR_ACCEPT');
  const envelope = fixture[mode];
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    expect(!init.method || init.method === 'GET').toBe(true);
    if (url === fixture.paths.jobs) return new Response(JSON.stringify(envelope), {headers: {'Content-Type': 'application/json'}});
    if (url === fixture.download.path && mode === 'approved') {
      return new Response(Uint8Array.from(atob(fixture.download.body_b64), char => char.charCodeAt(0)).buffer,
        {status: fixture.download.status, headers: fixture.download.headers});
    }
    throw new Error('Unexpected protocol request');
  });
  vi.stubGlobal('fetch', fetcher);
  const view = render(<CanvasNodeTaskStatus novelId={fixture.project_id} nodeId={nodeId}/>);
  const button = await screen.findByRole('button', {name: '预览原任务候选结果'});
  expect(screen.queryByRole('img')).toBeNull(); expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('原任务提示词')).toHaveProperty('value', envelope.items[0].prompt);
  fireEvent.click(button);
  const image = await screen.findByRole('img', {name: '原节点任务候选结果'});
  expect(view.container.textContent).not.toContain(envelope.items[0].asset_uri);
  if (mode === 'approved') {
    expect(image.getAttribute('src')).toBe('blob:captured-file-protocol');
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([fixture.paths.jobs, fixture.paths.jobs, fixture.download.path, fixture.paths.jobs]);
    expect(createUrl).toHaveBeenCalledTimes(1);
    const blob = createUrl.mock.calls[0][0] as Blob;
    expect(blob.size).toBe(fixture.approved_asset.size); expect(blob.type).toBe(fixture.approved_asset.media_type);
    view.unmount(); expect(revokeUrl).toHaveBeenCalledWith('blob:captured-file-protocol');
  } else {
    expect(image.getAttribute('src')).toBe(envelope.items[0].asset_uri);
    expect(fetcher).toHaveBeenCalledTimes(2); expect(createUrl).not.toHaveBeenCalled();
  }
});

it('accepts the first committed preview action after initializing the candidate lifecycle', async () => {
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    expect(url).toBe(fixture.paths.jobs);
    expect(!init.method || init.method === 'GET').toBe(true);
    return new Response(JSON.stringify(fixture.pending_inline), {headers: {'Content-Type': 'application/json'}});
  });
  vi.stubGlobal('fetch', fetcher);
  const owner = captureCanvasTaskOwner(fixture.project_id)!;
  const binding = readCanvasTaskBinding(owner, nodeId)!;
  const candidate = checkedCanvasTaskCandidate(binding, fixture.pending_inline.items[0])!;
  const unavailable = vi.fn();
  function FirstCommitHost() {
    // A host can act after child commit, before passive effects. An enabled
    // control must already have its owner/request lifecycle initialized.
    useLayoutEffect(() => {
      const button = screen.getByRole('button', {name: '预览原任务候选结果'}) as HTMLButtonElement;
      expect(button.disabled).toBe(false);
      button.click();
    }, []);
    return <CanvasTaskCandidateView candidate={candidate} binding={binding} isCurrent={() => true} onUnavailable={unavailable}/>;
  }
  render(<FirstCommitHost/>);
  await screen.findByRole('img', {name: '原节点任务候选结果'});
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(unavailable).not.toHaveBeenCalled();
});
