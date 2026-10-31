// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';

function screenplay(): CreativeDocument {
  return {
    ...newDocument('SCREENPLAY', 'chapter-1'),
    id: 'screenplay-1', version: 1, title: 'Harbor screenplay', status: 'DRAFT',
    created_at: '', updated_at: '', actor_id: 'author', source_evidence: {},
    scenes: [{ ...newScene(1, 'chapter-1'), id: 'scene-1', heading: 'The harbor' }],
  };
}

function suggestion(id: string): DirectorProposal {
  return {
    id, version: 1, status: 'NEEDS_REVIEW', source_document_id: 'screenplay-1',
    source_version: 1, title: `Harbor direction ${id}`, output_digest: `digest-${id}`,
    provenance: { model_called: false },
    director_notes: [{
      id: `note-${id}`, number: 1, scene_id: 'scene-1', note: 'Review the scene',
      shot_size: 'WIDE', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC',
      duration_seconds: 5, emotion: 'Tense', pacing: 'Slow',
      performance: 'Understated', blocking: 'Stand beside the rail',
    }],
  };
}

function response(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

function setup() {
  const created: DirectorProposal[] = [];
  const reviewed: { id: string; body: Record<string, unknown> }[] = [];
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/director-proposals') && init.method === 'GET') return response({ items: [] });
    if (url.endsWith('/director-proposals') && init.method === 'POST') {
      const proposal = suggestion(`proposal-${created.length + 1}`);
      created.push(proposal);
      return response(proposal);
    }
    if (url.endsWith('/review') && init.method === 'POST') {
      const id = url.split('/').at(-2)!;
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      reviewed.push({ id, body });
      return response({
        proposal: { ...suggestion(id), status: 'APPROVED', version: 2 },
        document: { ...screenplay(), id: 'director-1', mode: 'DIRECTOR', title: body.title },
      });
    }
    throw new Error(`Unexpected request ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  const onDocument = vi.fn(), onBusyChange = vi.fn();
  render(<AIDirectorPanel
    client={creativeClient('novel-1', { sessionToken: 'session-1' })}
    documents={[screenplay()]} canMutate={true} onDocument={onDocument}
    onDenied={vi.fn()} onBusyChange={onBusyChange} onOpenModels={() => {}}
  />);
  return { created, reviewed, onDocument, onBusyChange };
}

const prepareButton = () => screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement;
async function activateAndSettle(detail: number) {
  // Resolve the receipt and React updates before the next pointer activation.
  // A synchronous pair of clicks would exercise only the existing in-flight lock.
  await act(async () => { fireEvent.click(prepareButton(), { detail }); });
  expect(prepareButton().disabled).toBe(false);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('director proposal activation after a fast receipt', () => {
  it('keeps one native double-click bound to its first proposal through edited human review', async () => {
    const { created, reviewed, onDocument, onBusyChange } = setup();
    await screen.findByText('没有待审导演建议');

    await activateAndSettle(1);
    expect(onBusyChange).toHaveBeenLastCalledWith(false);
    expect(created.map(row => row.id)).toEqual(['proposal-1']);
    // Native double-clicks carry detail 1 then 2 even when the first response
    // arrives between them. The second click must not select a new proposal.
    await activateAndSettle(2);

    fireEvent.click(screen.getByText('场景调度 1', { exact: true }));
    fireEvent.change(screen.getByLabelText('建议 1 表演指导'), { target: { value: 'Pause, then look toward the window.' } });
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Human-reviewed harbor direction' } });
    fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '审核并采用' }), { detail: 1 }); });

    expect(onDocument).toHaveBeenCalledTimes(1);
    expect({ createdIds: created.map(row => row.id), reviewedIds: reviewed.map(row => row.id) }).toEqual({
      createdIds: ['proposal-1'], reviewedIds: ['proposal-1'],
    });
    expect(reviewed[0].body).toMatchObject({
      expected_version: 1, reviewed_output_digest: 'digest-proposal-1',
      title: 'Human-reviewed harbor direction',
      director_notes: [{ performance: 'Pause, then look toward the window.' }],
    });
  });

  it('still allows a later independent single-click to prepare another proposal', async () => {
    const { created } = setup();
    await screen.findByText('没有待审导演建议');
    await activateAndSettle(1);
    await activateAndSettle(1);
    expect(created.map(row => row.id)).toEqual(['proposal-1', 'proposal-2']);
    expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Harbor direction proposal-2');
  });

  it('preserves keyboard-style button activation with zero click detail', async () => {
    const { created } = setup();
    await screen.findByText('没有待审导演建议');
    await activateAndSettle(0);
    expect(created.map(row => row.id)).toEqual(['proposal-1']);
    expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Harbor direction proposal-1');
  });
});
