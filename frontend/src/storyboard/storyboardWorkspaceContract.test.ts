import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createStoryboardWorkspaceClient } from './storyboardWorkspaceClient';
import {
  directorGoalDraft, directorGoalView, directorProposalSuggestion, shotMove, shotMoves,
  storyboardScopeEnvelope, targetDraft, workspaceDirectorAdvice, workspaceReceipt,
} from './storyboardWorkspaceContract';
import { bindDraftToReceipt, sendToDraft } from './storyboardOps';
import {
  copy, directorAdvice, directorDocument, directorProposal, receiptWithVideo, storyboardReceipt,
} from './storyboardWorkspaceFixtures.testFixture';

const json = vi.fn();
const transport = { json } as unknown as StudioGraphTransport;
const client = (project = 'project-1', scope?: { projectId: string }) =>
  createStoryboardWorkspaceClient(project, transport, scope as never);
const codeOf = (run: () => unknown) => {
  try { run(); return 'NO_THROW'; } catch (reason) { return (reason as { problem?: { code?: string } }).problem?.code; }
};
/** 复用的解码器要求"请求的文档身份 === 回执里的文档身份"，所以这里用 fixture 自己的 id。 */
const DOCUMENT_ID = '89a4c387-9ff4-4b5b-919f-6755259868d5';

describe('storyboardWorkspaceClient 只读既有分镜端点', () => {
  it('读取分镜时只发出一个 GET，路径与既有消费者一致', async () => {
    json.mockReset();
    json.mockImplementation(async () => copy(storyboardReceipt()));
    const value = await client().readStoryboard(DOCUMENT_ID);
    expect(json.mock.calls).toHaveLength(1);
    expect(json.mock.calls[0]).toEqual([
      `/api/novels/project-1/experimental/creative/documents/${DOCUMENT_ID}/storyboard`, 'GET', undefined, undefined,
    ]);
    expect(value.contract).toBe('studio-storyboard/1');
    expect(value.shots).toHaveLength(2);
    expect(value.shots.map(shot => shot.shot_id)).toEqual(['shot-1', 'shot-2']);
  });

  it('文档标识在 URL 里被编码，并且请求路径不携带任何写动作', async () => {
    json.mockReset();
    json.mockImplementation(async () => copy(directorAdvice()));
    await client().readDirectorAdvice('director doc/one').catch(() => undefined);
    expect(json.mock.calls[0][0]).toBe(
      '/api/novels/project-1/experimental/creative/documents/director%20doc%2Fone/director-advice',
    );
    expect(json.mock.calls[0][1]).toBe('GET');
  });
  it('读取导演建议时只发出一个 GET，并且绝不写', async () => {
    json.mockReset();
    json.mockImplementation(async () => copy(directorAdvice()));
    const value = await client().readDirectorAdvice('director-doc');
    expect(json.mock.calls[0]).toEqual([
      '/api/novels/project-1/experimental/creative/documents/director-doc/director-advice', 'GET', undefined, undefined,
    ]);
    expect(value.advice_only).toBe(true);
    expect(value.automatic_apply).toBe(false);
    expect(json.mock.calls.every(call => call[1] === 'GET')).toBe(true);
  });

  it('未知字段或身份不符都会被既有解码器拒绝，并带上稳定机器码', async () => {
    json.mockReset();
    const tampered = copy(storyboardReceipt()) as unknown as Record<string, unknown>;
    tampered.append = true;
    json.mockResolvedValueOnce(tampered);
    await expect(client().readStoryboard(DOCUMENT_ID)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });

    json.mockImplementationOnce(async () => copy(storyboardReceipt()));
    await expect(client().readStoryboard('another-document')).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it('协作范围指向别的项目时立刻拒绝，不发请求', async () => {
    json.mockReset();
    const foreign = client('project-1', { projectId: 'project-2' });
    await expect(foreign.readStoryboard(DOCUMENT_ID)).rejects.toMatchObject({ problem: { code: 'STUDIO_STORYBOARD_SCOPE_MISMATCH' } });
    await expect(foreign.readDirectorAdvice(DOCUMENT_ID)).rejects.toMatchObject({ problem: { code: 'STUDIO_STORYBOARD_SCOPE_MISMATCH' } });
    expect(json).not.toHaveBeenCalled();
  });

  it('无效的项目或文档标识在本地就被拒绝', () => {
    json.mockReset();
    expect(codeOf(() => createStoryboardWorkspaceClient('', transport))).toBe('STUDIO_STORYBOARD_SCOPE_MISMATCH');
    expect(codeOf(() => createStoryboardWorkspaceClient('x'.repeat(241), transport))).toBe('STUDIO_STORYBOARD_SCOPE_MISMATCH');
    return client().readStoryboard('  ').catch(reason => {
      expect((reason as { problem: { code: string } }).problem.code).toBe('STUDIO_RESPONSE_INVALID');
      expect(json).not.toHaveBeenCalled();
    });
  });

  it('原 owner 的 507/401 码被翻译成有界中文文案，机器码保留', async () => {
    json.mockReset();
    json.mockRejectedValueOnce(new ApiError({
      status: 507, code: 'CREATIVE_STORAGE_LOW_SPACE', message: 'raw server text',
    }));
    await expect(client().readStoryboard(DOCUMENT_ID)).rejects.toMatchObject({
      problem: { code: 'CREATIVE_STORAGE_LOW_SPACE', message: '项目所在磁盘可用空间不足，本次读取未完成。请释放空间后重试。' },
    });
    json.mockRejectedValueOnce(new ApiError({ status: 401, code: 'HTTP_401', message: 'raw' }));
    await expect(client().readStoryboard(DOCUMENT_ID)).rejects.toMatchObject({ problem: { status: 401 } });
  });
});

describe('storyboardWorkspaceContract 严格解码', () => {
  it('分镜回执仍由既有解码器负责，并且核对文档身份', () => {
    const value = workspaceReceipt(copy(storyboardReceipt()), DOCUMENT_ID);
    expect(value.document_snapshot.version).toBe(4);
    expect(() => workspaceReceipt(copy(storyboardReceipt()), 'other-doc')).toThrowError();
    expect(() => workspaceReceipt(copy(storyboardReceipt()), '')).toThrowError();
    expect(() => workspaceReceipt(copy(storyboardReceipt()), 'x'.repeat(241))).toThrowError();
  });

  it('导演建议回执同样复用既有解码器', () => {
    const advice = directorAdvice();
    expect(workspaceDirectorAdvice(copy(advice), advice.document_snapshot.id).notes.length).toBe(advice.notes.length);
    expect(() => workspaceDirectorAdvice(copy(advice), 'other-doc')).toThrowError();
  });

  it('连接信封核对项目与范围，不匹配就是 SCOPE_MISMATCH', () => {
    const envelope = { novel_id: 'project-1', scope_key: 'local:project-1', document_id: 'doc-1', branch_id: null, mode: 'local' as const };
    expect(storyboardScopeEnvelope(copy(envelope), 'project-1')).toEqual(envelope);
    expect(codeOf(() => storyboardScopeEnvelope(copy(envelope), 'project-2'))).toBe('STUDIO_STORYBOARD_SCOPE_MISMATCH');
    expect(codeOf(() => storyboardScopeEnvelope(copy(envelope), 'project-1', { ...envelope, document_id: 'other' })))
      .toBe('STUDIO_STORYBOARD_SCOPE_MISMATCH');
    expect(codeOf(() => storyboardScopeEnvelope({ ...envelope, extra: 1 }, 'project-1'))).toBe('STUDIO_RESPONSE_INVALID');
  });

  it('move 解码拒绝未知键、自指与重复', () => {
    expect(shotMove({ shot_id: 'a', before_shot_id: null })).toEqual({ shot_id: 'a', before_shot_id: null });
    expect(codeOf(() => shotMove({ shot_id: 'a', before_shot_id: null, extra: 1 }))).toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => shotMoves([{ shot_id: 'a', before_shot_id: 'a' }], ['a']))).toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => shotMoves([{ shot_id: 'a', before_shot_id: null }, { shot_id: 'a', before_shot_id: null }], ['a'])))
      .toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => shotMoves([{ shot_id: 'z', before_shot_id: null }], ['a']))).toBe('STUDIO_RESPONSE_INVALID');
  });

  it('导演文档投影读出已采用内容，并如实标注上游来源', () => {
    const view = directorGoalView(directorDocument({
      source_documents: { 'screenplay-doc': { version: 3, digest: 'b'.repeat(64) } },
    }), 'project-1', 'director-doc', null);
    expect(view.goals).toHaveLength(1);
    expect(view.goals[0].note_id).toBe('note-1');
    expect(view.goals[0].adopted.shot_size).toBe('MEDIUM');
    expect(view.goals[0].adopted.duration_seconds).toBe(5);
    expect(view.goals[0].suggestion).toBeNull();
    expect(view.goals[0].source_document).toEqual({ id: 'screenplay-doc', version: 3, digest: 'b'.repeat(64) });
    expect(view.document).toEqual({ id: 'director-doc', version: 2, digest: '' });
  });

  it('导演文档投影拒绝错误模式、未知键与越界时长', () => {
    expect(codeOf(() => directorGoalView(directorDocument({ mode: 'STORYBOARD' }), 'project-1', 'director-doc', null)))
      .toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => directorGoalView(directorDocument({ extra: true }), 'project-1', 'director-doc', null)))
      .toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => directorGoalView(directorDocument(), 'project-1', 'other-doc', null)))
      .toBe('STUDIO_STORYBOARD_SCOPE_MISMATCH');
    const long = directorDocument();
    (long.director_notes as Record<string, unknown>[])[0].duration_seconds = 601;
    expect(codeOf(() => directorGoalView(long, 'project-1', 'director-doc', null))).toBe('STUDIO_RESPONSE_INVALID');
    const noteExtra = directorDocument();
    (noteExtra.director_notes as Record<string, unknown>[])[0].unknown_note_field = 1;
    expect(codeOf(() => directorGoalView(noteExtra, 'project-1', 'director-doc', null))).toBe('STUDIO_RESPONSE_INVALID');
  });

  it('待审建议与已采用内容分开解码：状态、摘要与质量核验都来自原 owner', () => {
    const suggestion = directorProposalSuggestion(directorProposal(), 'director-doc');
    expect(suggestion.status).toBe('NEEDS_REVIEW');
    expect(suggestion.model_called).toBe(false);
    expect(suggestion.quality_verification).toBe('HUMAN_REVIEW_REQUIRED');
    expect(suggestion.notes).toHaveLength(1);
    expect(suggestion.output_digest).toBe('a'.repeat(64));
    expect(codeOf(() => directorProposalSuggestion(directorProposal({ source_document_id: 'other' }), 'director-doc')))
      .toBe('STUDIO_STORYBOARD_SCOPE_MISMATCH');
    expect(codeOf(() => directorProposalSuggestion(directorProposal({ status: 'EXECUTING' }), 'director-doc')))
      .toBe('STUDIO_RESPONSE_INVALID');
    expect(directorProposalSuggestion(directorProposal({ status: 'CANCELLED' }), 'director-doc').output_digest).toBeNull();
  });

  it('目标草稿只在本地：时长必须是 1–3 位数字，未知键被拒绝', () => {
    const draft = directorGoalDraft({
      scene_id: 'scene-1', note_id: 'note-1', shot_size: 'WIDE', camera_angle: 'LOW',
      camera_motion: 'PAN', duration_seconds: '12', emotion: '', pacing: '', performance: '',
    });
    expect(draft.duration_seconds).toBe('12');
    expect(codeOf(() => directorGoalDraft({ ...draft, duration_seconds: '1000' }))).toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => directorGoalDraft({ ...draft, duration_seconds: 'abc' }))).toBe('STUDIO_RESPONSE_INVALID');
    expect(codeOf(() => directorGoalDraft({ ...draft, extra: 1 }))).toBe('STUDIO_RESPONSE_INVALID');
  });

  it('送往草稿复核必须与当前回执逐字段一致，并且不通过任何绑定替换', () => {
    const base = receiptWithVideo();
    const bound = bindDraftToReceipt(sendToDraft('VIDEO', base.shots[1]), base);
    const checked = targetDraft(copy(bound), 'VIDEO', base);
    expect(checked.shot_id).toBe('shot-2');
    expect(checked.bindings.VIDEO?.job.id).toBe('video-job');
    expect(checked.document_version).toBe(base.document_snapshot.version);

    const tamperedVideo = copy(bound);
    (tamperedVideo.bindings.VIDEO as { job: { id: string } }).job.id = 'another-job';
    expect(codeOf(() => targetDraft(tamperedVideo, 'VIDEO', base))).toBe('STUDIO_RESPONSE_INVALID');

    const tamperedImage = copy(bound);
    (tamperedImage.bindings.IMAGE as { version: number }).version = 99;
    expect(codeOf(() => targetDraft(tamperedImage, 'VIDEO', base))).toBe('STUDIO_RESPONSE_INVALID');

    const wrongTarget = copy(bound);
    wrongTarget.target = 'TIMELINE';
    expect(codeOf(() => targetDraft(wrongTarget, 'VIDEO', base))).toBe('STUDIO_RESPONSE_INVALID');

    const staleShot = copy(bound);
    staleShot.shot_version = 9;
    expect(codeOf(() => targetDraft(staleShot, 'VIDEO', base))).toBe('STUDIO_RESPONSE_INVALID');

    const unknownShot = copy(bound);
    unknownShot.shot_id = 'missing';
    expect(codeOf(() => targetDraft(unknownShot, 'VIDEO', base))).toBe('STUDIO_RESPONSE_INVALID');

    const badOrder = copy(bound);
    badOrder.order_shot_ids = ['shot-2', 'shot-2'];
    expect(codeOf(() => targetDraft(badOrder, 'VIDEO', base))).toBe('STUDIO_RESPONSE_INVALID');
  });
});
