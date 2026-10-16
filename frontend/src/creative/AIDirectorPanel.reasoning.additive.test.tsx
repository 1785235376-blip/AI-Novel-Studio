// @vitest-environment jsdom
// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';

function source(): CreativeDocument { return { ...newDocument('SCREENPLAY', 'chapter-1'), id: 'screenplay-1', version: 4, title: 'Source screenplay', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, scenes: [{ ...newScene(1, 'chapter-1'), id: 'scene-1', heading: 'The harbor' }] }; }
function suggestion(): DirectorProposal { return { id: 'proposal-1', version: 2, status: 'NEEDS_REVIEW', source_document_id: 'screenplay-1', source_version: 4, title: 'Harbor direction', director_notes: [{ id: 'note-1', number: 1, scene_id: 'scene-1', note: 'Let the silence build', shot_size: 'WIDE', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, emotion: 'Tense', pacing: 'Slow', performance: 'Understated', blocking: 'Stand beside the rail' }], output_digest: 'reviewed-digest', provenance: { model_called: false } }; }
function response(body: unknown, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => body }; }

function setup(options: { proposals?: DirectorProposal[]; canMutate?: boolean; override?: (url: string, init: RequestInit) => unknown } = {}) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const result = options.override?.(url, init); if (result !== undefined) return await result;
    if (url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/director-proposals') && init?.method === 'GET') return response({ items: options.proposals || [] });
    if (url.endsWith('/director-proposals') && init?.method === 'POST') return response(suggestion());
    if (url.endsWith('/review')) return response({ proposal: { ...suggestion(), status: 'APPROVED', version: 3 }, document: { ...source(), mode: 'DIRECTOR', id: 'director-1', title: JSON.parse(String(init.body)).title } });
    if (url.endsWith('/cancel')) return response({ ...suggestion(), status: 'CANCELLED', version: 3 });
    throw new Error(`Unexpected request ${init?.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  const onDocument = vi.fn(), onDenied = vi.fn(), onBusyChange = vi.fn();
  const client = creativeClient('novel-1', { sessionToken: 'captured-session', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'captured-branch' } });
  const view = render(<AIDirectorPanel client={client} documents={[source()]} canMutate={options.canMutate ?? true} onDocument={onDocument} onDenied={onDenied} onBusyChange={onBusyChange} onOpenModels={() => {}} />);
  return { fetchMock, onDocument, onDenied, onBusyChange, view, mutations: () => fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET') };
}
async function prepare() { fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); await screen.findByLabelText('采用后的导演文档标题'); }
const reviewCheck = () => screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档');
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('AI director local proposal and explicit review', () => {
  it('shows estimated totals and editable model reasoning separately from auxiliary rules', async () => {
    const candidate = suggestion(); candidate.provenance.model_called = true;
    candidate.director_notes[0].planning = { rationale: 'A reaction motivates the close-up', sequence_reason: 'Follow the reveal', duration_reason: 'Estimated pause', uncertainty: 'Axis unknown', assumptions: ['Space unverified'], alternatives: [{ choice: 'Hold wide', tradeoff: 'Less facial detail' }], evidence: [{ scene_id: 'scene-1', field: 'heading', dialogue_index: null, excerpt: 'The harbor' }] };
    const { mutations } = setup({ proposals: [candidate] });
    fireEvent.click(await screen.findByRole('button', { name: /Harbor direction/ }));
    expect(screen.getByText(/预计总时长 5 秒/)).toBeTruthy();
    expect(screen.getByText('模型产出 · 需审核')).toBeTruthy();
    expect(screen.getByText('规则辅助检查（原始候选）')).toBeTruthy();
    fireEvent.click(reviewCheck());
    fireEvent.change(screen.getByLabelText('建议 1 决策理由'), { target: { value: 'Reviewed motivation' } });
    expect((reviewCheck() as HTMLInputElement).checked).toBe(false);
    fireEvent.change(screen.getByLabelText('建议 1 时长（秒）'), { target: { value: '9' } });
    expect(screen.getByText(/预计总时长 9 秒/)).toBeTruthy();
    fireEvent.click(reviewCheck()); fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
    await screen.findByText('已创建导演文档。小说正文保持原有保存与审核流程。');
    expect(JSON.parse(String(mutations()[0][1]?.body)).director_notes[0].planning).toMatchObject({ rationale: 'Reviewed motivation', assumptions: ['Space unverified'] });
  });

  it('keeps the shared genre field bounded in preparation and review without losing the other target fields', async () => {
    const { mutations } = setup(); await screen.findByText('没有待审导演建议');
    const prepared = screen.getByLabelText('建议准备 文档类型 / 题材') as HTMLInputElement;
    fireEvent.change(prepared, { target: { value: '🎬'.repeat(2001) } });
    expect((screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement).disabled).toBe(true);
    expect(prepared.value).toBe('🎬'.repeat(2001)); expect(mutations()).toHaveLength(0);
    fireEvent.change(prepared, { target: { value: '🎬'.repeat(2000) } });
    fireEvent.change(screen.getByLabelText('建议准备 视觉风格'), { target: { value: '原有风格' } });
    await prepare();
    expect(JSON.parse(String(mutations()[0][1]?.body)).visual_target).toMatchObject({ genre: '🎬'.repeat(2000), style: '原有风格' });
    const reviewed = screen.getByLabelText('建议审核 文档类型 / 题材') as HTMLInputElement;
    fireEvent.change(reviewed, { target: { value: '题'.repeat(2001) } }); fireEvent.click(reviewCheck());
    expect((screen.getByRole('button', { name: '审核并采用' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(reviewed, { target: { value: '审核题材' } }); expect((reviewCheck() as HTMLInputElement).checked).toBe(false);
    fireEvent.click(reviewCheck()); fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
    await screen.findByText('已创建导演文档。小说正文保持原有保存与审核流程。');
    expect(JSON.parse(String(mutations()[1][1]?.body))).toMatchObject({ expected_version: 2, visual_target: { genre: '审核题材' } });
  });

});
