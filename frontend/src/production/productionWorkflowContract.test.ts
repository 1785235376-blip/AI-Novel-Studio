import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import {
  productionWorkflowIntent, productionWorkflowIntentRequest, productionWorkflowProjection,
} from './productionWorkflowContract';
import { PRODUCTION_WORKFLOW_MODULES, PRODUCTION_WORKFLOW_START_ACTION } from './productionWorkflowTypes';

/** Protocol fixture only. It proves the frozen shape, not product or runtime acceptance. */
type FixtureScope = { mode: string; novel_id: string; workspace_id?: string; project_id?: string; storyline_id?: string; branch_id?: string };
function fixture() {
  const scope: FixtureScope = { mode: 'local', novel_id: 'studio-project' };
  return {
    schema_version: 1, contract: 'studio-production-workflow/1', project_id: 'studio-project',
    scope,
    advisory_only: true, execution_authority: false, generated_at: '2026-10-14T09:41:59.123456+00:00',
    project_start: {
      state: 'STARTED', entry_kind: 'NEUTRAL_STUDIO', incarnation: 'file:2f1a9c3e-0000-4000-8000-000000000000',
      has_creative_documents: true,
      start_action: { method: 'POST', path: '/api/experimental/projects', requires_original_host_session: true },
    },
    creative_intent: {
      version: 3, preset: 'IMAGE', editable: true, history_retained: true,
      values: [
        { intent_id: 'novel_writing', label: '小说创作', selected: false, custom: false },
        { intent_id: 'image_design', label: '图片设计', selected: true, custom: false },
        { intent_id: 'custom', label: '我的短片', selected: true, custom: true },
      ],
    },
    modules: [
      { id: 'director', label: '导演', status: 'REVIEWED', document_count: 2, asset_count: 0, job_count: 0, blocked_reasons: [], owner: 'DirectorService', next_action: '素材已复核' },
      { id: 'storyboard', label: '分镜', status: 'PLANNED', document_count: 1, asset_count: 0, job_count: 0, blocked_reasons: [], owner: 'StoryboardWorkspace', next_action: '已规划，等待素材执行' },
      { id: 'image', label: '图像', status: 'REVIEW_PENDING', document_count: 0, asset_count: 3, job_count: 2, blocked_reasons: ['PRIVATE_CANDIDATES_AWAITING_REVIEW'], owner: 'ImageJobService', next_action: '有待人工复核的私有候选' },
      { id: 'video', label: '视频', status: 'NOT_STARTED', document_count: 0, asset_count: 0, job_count: 0, blocked_reasons: [], owner: 'StudioVideoExecution', next_action: '尚未开始' },
      { id: 'audio', label: '音频', status: 'IN_PRODUCTION', document_count: 0, asset_count: 2, job_count: 1, blocked_reasons: [], owner: 'StudioAudioExecution', next_action: '素材进行中' },
      { id: 'timeline', label: '时间线', status: 'NOT_STARTED', document_count: 0, asset_count: 0, job_count: 0, blocked_reasons: [], owner: 'VideoAssemblyService', next_action: '尚未开始' },
      { id: 'asset', label: '资产', status: 'NOT_STARTED', document_count: 0, asset_count: 1, job_count: 0, blocked_reasons: [], owner: 'AssetLibraryService', next_action: '尚未开始' },
    ],
    asset_overview: { total: 4, by_kind: { image: 2, audio: 1, video: 0, text: 0, other: 1 }, private_pending_review: 2, reviewed: 1 },
    dashboard: { stages_total: 7, stages_started: 4, stages_reviewed: 1, open_reviews: 2, blocked_stages: ['image'] },
  };
}
const module = (value: ReturnType<typeof fixture>, index: number) => value.modules[index] as Record<string, unknown>;
const clone = () => structuredClone(fixture());
const reason = (value: unknown) => value as ApiError;

describe('unified production workflow projection contract', () => {
  it('accepts the exact frozen shape and re-derives every counter', () => {
    const value = productionWorkflowProjection(fixture(), 'studio-project');
    expect(value.contract).toBe('studio-production-workflow/1');
    expect(value.advisory_only).toBe(true);
    expect(value.execution_authority).toBe(false);
    expect(value.modules.map(item => item.id)).toEqual([...PRODUCTION_WORKFLOW_MODULES]);
    expect(value.dashboard).toEqual({ stages_total: 7, stages_started: 4, stages_reviewed: 1, open_reviews: 2, blocked_stages: ['image'] });
    expect(value.asset_overview.by_kind).toEqual({ image: 2, audio: 1, video: 0, text: 0, other: 1 });
    expect(value.project_start.start_action).toEqual(PRODUCTION_WORKFLOW_START_ACTION);
    expect(value.creative_intent.values[2]).toEqual({ intent_id: 'custom', label: '我的短片', selected: true, custom: true });
  });

  it('rejects any unknown key at every level', () => {
    const top = clone(); Object.assign(top, { extra: true });
    const scope = clone(); Object.assign(scope.scope, { principal_id: 'private-actor' });
    const intent = clone(); Object.assign(intent.creative_intent, { note: 'private' });
    const item = clone(); Object.assign(module(item, 0), { progress: 50 });
    const kinds = clone(); Object.assign(kinds.asset_overview.by_kind, { archive: 1 });
    const board = clone(); Object.assign(board.dashboard, { stages_blocked: 1 });
    const start = clone(); Object.assign(start.project_start, { started_by: 'someone' });
    for (const value of [top, scope, intent, item, kinds, board, start]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('rejects a wrong module order, a wrong count and a duplicated module', () => {
    const swapped = clone();
    [swapped.modules[2], swapped.modules[3]] = [swapped.modules[3], swapped.modules[2]];
    const missing = clone(); missing.modules.splice(4, 1);
    const extra = clone(); extra.modules.push(structuredClone(extra.modules[6]));
    const duplicated = clone(); duplicated.modules[6] = structuredClone(duplicated.modules[2]);
    for (const value of [swapped, missing, extra, duplicated]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('rejects an unknown status, a non-boolean flag and out-of-range integers', () => {
    const status = clone(); Object.assign(module(status, 0), { status: 'DONE' });
    const flag = clone(); Object.assign(module(flag, 1), { document_count: true });
    const negative = clone(); Object.assign(module(negative, 1), { document_count: -1 });
    const fractional = clone(); Object.assign(module(fractional, 1), { asset_count: 1.5 });
    const version = clone(); version.creative_intent.version = -1;
    const huge = clone(); huge.dashboard.stages_started = 8;
    const unsafe = clone(); module(unsafe, 5).job_count = Number.MAX_SAFE_INTEGER + 2;
    for (const value of [status, flag, negative, fractional, version, huge, unsafe]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('rejects over-long strings and any control character', () => {
    const label = clone(); module(label, 0).label = '导'.repeat(121);
    const owner = clone(); module(owner, 0).owner = 'S'.repeat(121);
    const intentLabel = clone(); intentLabel.creative_intent.values[0].label = 'x'.repeat(121);
    const intentId = clone(); intentId.creative_intent.values[0].intent_id = 'a'.repeat(65);
    const blocked = clone(); module(blocked, 2).blocked_reasons = ['x'.repeat(301)];
    const control = clone(); module(control, 0).label = '导\u0000演';
    const newline = clone(); module(newline, 0).owner = 'Director\nService';
    const blank = clone(); module(blank, 0).owner = '   ';
    for (const value of [label, owner, intentLabel, intentId, blocked, control, newline, blank]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('throws a scope mismatch code for a foreign project, branch or mode', () => {
    expect(() => productionWorkflowProjection(fixture(), 'other-project')).toThrow(ApiError);
    expect(reason(catchOf(() => productionWorkflowProjection(fixture(), 'other-project'))).problem.code).toBe('PRODUCTION_WORKFLOW_SCOPE_MISMATCH');
    const novel = clone(); novel.scope.novel_id = 'other-project';
    const branch = clone(); Object.assign(branch.scope, { branch_id: 'other-branch' });
    const mode = clone(); mode.scope.mode = 'collaboration';
    for (const value of [novel, branch, mode]) {
      expect(reason(catchOf(() => productionWorkflowProjection(value, 'studio-project'))).problem.code).toBe('PRODUCTION_WORKFLOW_SCOPE_MISMATCH');
    }
    const collaboration = clone();
    collaboration.scope = { mode: 'collaboration', novel_id: 'studio-project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' };
    expect(productionWorkflowProjection(collaboration, 'studio-project',
      { mode: 'collaboration', novel_id: 'studio-project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' }).scope.branch_id).toBe('branch');
    const wrongBranch = structuredClone(collaboration);
    wrongBranch.scope.branch_id = 'changed-after-capture';
    expect(() => productionWorkflowProjection(wrongBranch, 'studio-project',
      { mode: 'collaboration', novel_id: 'studio-project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' })).toThrow(ApiError);
  });

  it('rejects a dashboard that disagrees with the modules or the asset overview', () => {
    const started = clone(); started.dashboard.stages_started = 5;
    const reviewed = clone(); reviewed.dashboard.stages_reviewed = 0;
    const reviews = clone(); reviews.dashboard.open_reviews = 1;
    const stages = clone(); stages.dashboard.stages_total = 8;
    const missingBlocker = clone(); missingBlocker.dashboard.blocked_stages = [];
    const unknown = clone(); unknown.dashboard.blocked_stages = ['video'];
    const duplicate = clone(); duplicate.dashboard.blocked_stages = ['image', 'image'];
    const invented = clone(); invented.dashboard.blocked_stages = ['image', 'playwright'];
    for (const value of [started, reviewed, reviews, stages, missingBlocker, unknown, duplicate, invented]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('rejects an inconsistent asset overview', () => {
    const kinds = clone(); delete (kinds.asset_overview.by_kind as Record<string, unknown>).other;
    const sum = clone(); sum.asset_overview.by_kind.image = 5;
    const overlap = clone(); overlap.asset_overview.private_pending_review = 3; overlap.asset_overview.reviewed = 2;
    const negative = clone(); negative.asset_overview.by_kind.other = -1;
    for (const value of [kinds, sum, overlap, negative]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('never accepts a promoted projection, a foreign contract or a rewritten start action', () => {
    const advisory = clone(); advisory.advisory_only = false;
    const authority = clone(); authority.execution_authority = true;
    const schema = clone(); schema.schema_version = 2;
    const contract = clone(); contract.contract = 'studio-production-workflow/2';
    const entry = clone(); entry.project_start.entry_kind = 'LEGACY';
    const method = clone(); Object.assign(method.project_start.start_action, { method: 'GET' });
    const host = clone(); Object.assign(host.project_start.start_action, { requires_original_host_session: false });
    const state = clone(); state.project_start.state = 'PAUSED';
    const badIncarnation = clone(); badIncarnation.project_start.incarnation = '../../etc/passwd';
    for (const value of [advisory, authority, schema, contract, entry, method, host, state, badIncarnation]) {
      expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    }
  });

  it('requires a UTC timestamp and normalizes an absent preset to null', () => {
    const utc = clone(); utc.generated_at = '2026-10-14T09:41:59Z';
    expect(productionWorkflowProjection(utc, 'studio-project').generated_at).toBe('2026-10-14T09:41:59Z');
    const local = clone(); local.generated_at = '2026-10-14T09:41:59';
    const offset = clone(); offset.generated_at = '2026-10-14T09:41:59+08:00';
    const garbage = clone(); garbage.generated_at = 'yesterday';
    for (const value of [local, offset, garbage]) expect(() => productionWorkflowProjection(value, 'studio-project')).toThrow(ApiError);
    const absent = clone(); delete (absent.creative_intent as Record<string, unknown>).preset;
    expect(productionWorkflowProjection(absent, 'studio-project').creative_intent.preset).toBeNull();
    const invented = clone(); invented.creative_intent.preset = 'CINEMATIC';
    expect(() => productionWorkflowProjection(invented, 'studio-project')).toThrow(ApiError);
  });
});

function catchOf(work: () => unknown): ApiError {
  try { work(); } catch (reason) { return reason as ApiError; }
  throw new Error('expected the contract to refuse this value');
}

describe('creative intent response and request contracts', () => {
  it('accepts the intent view and refuses duplicates, foreign ids and a read-only claim', () => {
    const value = productionWorkflowIntent(fixture().creative_intent);
    expect(value.version).toBe(3);
    expect(value.preset).toBe('IMAGE');
    expect(value.values.map(item => item.intent_id)).toEqual(['novel_writing', 'image_design', 'custom']);
    const duplicate = structuredClone(fixture().creative_intent); duplicate.values[1].intent_id = 'novel_writing';
    const foreign = structuredClone(fixture().creative_intent); foreign.values[0].intent_id = 'Image-Design';
    const readOnly = structuredClone(fixture().creative_intent); readOnly.editable = false;
    const noHistory = structuredClone(fixture().creative_intent); noHistory.history_retained = false;
    for (const candidate of [duplicate, foreign, readOnly, noHistory]) expect(() => productionWorkflowIntent(candidate)).toThrow(ApiError);
  });

  it('validates the outgoing replacement before it reaches the original owner', () => {
    const request = productionWorkflowIntentRequest({
      expected_version: 3, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }], preset: 'IMAGE',
    });
    expect(request).toEqual({ expected_version: 3, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }], preset: 'IMAGE' });
    expect(productionWorkflowIntentRequest({ expected_version: null, values: [] })).toEqual({ expected_version: null, values: [] });
    for (const candidate of [
      { expected_version: -1, values: [] },
      { expected_version: 3, values: [{ intent_id: 'custom', label: '', selected: true }] },
      { expected_version: 3, values: [{ intent_id: 'custom', label: 'x'.repeat(121), selected: true }] },
      { expected_version: 3, values: [{ intent_id: 'custom', label: 'ok', selected: 'yes' }] },
      { expected_version: 3, values: [{ intent_id: 'custom', label: 'ok', selected: true, custom: true }] },
      { expected_version: 3, values: [{ intent_id: 'custom', label: 'ok', selected: true }, { intent_id: 'custom', label: 'ok', selected: false }] },
      { expected_version: 3, values: [], preset: 'CINEMATIC' },
      { expected_version: 3, values: [], note: 'not part of the owner contract' },
      { expected_version: 3, values: new Array(12).fill({ intent_id: 'custom', label: 'ok', selected: false }) },
    ]) expect(() => productionWorkflowIntentRequest(candidate)).toThrow(ApiError);
  });
});
