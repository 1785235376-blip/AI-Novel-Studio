import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { studioEntryProjects, studioIntentRequest, studioIntentState } from './studioEntryContract';
import { STUDIO_INTENT_CATALOG, STUDIO_INTENT_IDS } from './studioEntryTypes';

/** Protocol fixtures only; they prove the validators, not runtime acceptance. */
const row = (patch: Record<string, unknown> = {}) => ({
  id: 'novel-1', title: '我的第一个项目', updated_at: '2026-10-14T09:41:59+00:00',
  entry_kind: 'NEUTRAL_STUDIO', genre: '科幻', status: 'ACTIVE', ...patch,
});
const values = (selected: string[] = [], customLabel = '我的短片') => STUDIO_INTENT_CATALOG.map(entry => ({
  intent_id: entry.intent_id,
  label: entry.intent_id === 'custom' && selected.includes('custom') ? customLabel : entry.label,
  selected: selected.includes(entry.intent_id),
  custom: entry.custom,
}));
const intentState = (patch: Record<string, unknown> = {}) => ({
  version: 1, preset: 'IMAGE', values: values(), editable: true, history_retained: true, ...patch,
});
/** Both validators and the outgoing request builder must refuse; only ApiError counts as a refusal. */
function refusalOf(work: () => unknown): ApiError {
  try { work(); } catch (reason) {
    if (reason instanceof ApiError) return reason;
    throw reason;
  }
  throw new Error('expected this call to be refused');
}

beforeEach(() => { vi.restoreAllMocks(); });

describe('studio entry project rows', () => {
  it('accepts the owner rows this entry needs, including the optional fields', () => {
    const rows = studioEntryProjects([row(), row({ id: 'novel-2', updated_at: undefined, updated: '2026-10-13T01:02:03Z', entry_kind: undefined, genre: undefined, status: undefined, title: '第二个项目' })]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ id: 'novel-1', title: '我的第一个项目', entry_kind: 'NEUTRAL_STUDIO', updated_at: '2026-10-14T09:41:59+00:00' });
    expect(rows[1]).toMatchObject({ id: 'novel-2', updated_at: '2026-10-13T01:02:03Z', entry_kind: null, genre: null, status: null });
    expect(studioEntryProjects([])).toEqual([]);
  });

  it('refuses an unknown key, a control character, an unbounded title and a path-like id', () => {
    const cases: unknown[] = [
      [row({ can_mutate: true })],
      [row({ title: '带\u0000控制字符' })],
      [row({ title: 'x'.repeat(201) })],
      [row({ id: '../../etc/passwd' })],
      [row({ id: '' })],
      [row({ updated_at: 'yesterday' })],
      row(),
      null,
      'rows',
    ];
    for (const candidate of cases) {
      const failure = refusalOf(() => studioEntryProjects(candidate));
      expect(failure.problem.code).toBe('STUDIO_ENTRY_RESPONSE_INVALID');
      expect(failure.message).toContain('项目入口数据不可用');
    }
  });
});

describe('studio entry intent state', () => {
  it('mirrors the Phase 7 creative_intent shape and keeps the custom marker', () => {
    const state = studioIntentState(intentState({ values: values(['image_design', 'custom'], '我的短片') }), 'novel-1');
    expect(state.version).toBe(1);
    expect(state.preset).toBe('IMAGE');
    expect(state.editable).toBe(true);
    expect(state.history_retained).toBe(true);
    expect(state.values.map(item => item.intent_id)).toEqual([...STUDIO_INTENT_IDS]);
    expect(state.values.find(item => item.intent_id === 'image_design')?.selected).toBe(true);
    expect(state.values.find(item => item.intent_id === 'custom')).toMatchObject({ label: '我的短片', selected: true, custom: true });
  });

  it('normalizes an absent or lower-case preset and a version zero', () => {
    expect(studioIntentState(intentState({ version: 0, preset: undefined }), 'novel-1').preset).toBeNull();
    expect(studioIntentState(intentState({ preset: null }), 'novel-1').preset).toBeNull();
    expect(studioIntentState(intentState({ version: 0 }), 'novel-1').version).toBe(0);
    expect(studioIntentState(intentState({ preset: 'mixed' }), 'novel-1').preset).toBe('MIXED');
  });

  it('refuses a duplicated intent, an unknown identifier, an unbounded label and a foreign scope', () => {
    const first = values()[0];
    const duplicated = [...values().slice(0, 5), { ...first }];
    const cases: { value: unknown; projectId: string; scope?: { project_id: string }; code: string }[] = [
      { value: intentState({ values: duplicated }), projectId: 'novel-1', code: 'STUDIO_ENTRY_RESPONSE_INVALID' },
      { value: intentState({ values: [{ intent_id: 'NOVEL-WRITING', label: '小说创作', selected: true, custom: false }] }), projectId: 'novel-1', code: 'STUDIO_ENTRY_RESPONSE_INVALID' },
      { value: intentState({ values: [{ intent_id: 'custom', label: 'x'.repeat(121), selected: true, custom: true }] }), projectId: 'novel-1', code: 'STUDIO_ENTRY_RESPONSE_INVALID' },
      { value: intentState({ values: [{ intent_id: 'custom', label: '自定义', selected: true, custom: true, note: 'no' }] }), projectId: 'novel-1', code: 'STUDIO_ENTRY_RESPONSE_INVALID' },
      { value: intentState({ version: -1 }), projectId: 'novel-1', code: 'STUDIO_ENTRY_RESPONSE_INVALID' },
      { value: intentState({ values: 'none' }), projectId: 'novel-1', code: 'STUDIO_ENTRY_RESPONSE_INVALID' },
      { value: intentState({ values: [] }), projectId: 'novel-1', scope: { project_id: 'novel-9' }, code: 'STUDIO_ENTRY_SCOPE_MISMATCH' },
    ];
    for (const testCase of cases) {
      const failure = refusalOf(() => studioIntentState(testCase.value, testCase.projectId, testCase.scope));
      expect(failure.problem.code).toBe(testCase.code);
    }
  });
});

describe('studio intent request', () => {
  it('accepts the frozen request shape and normalizes the preset case', () => {
    const request = studioIntentRequest({
      expected_version: 0, preset: 'audio',
      values: [{ intent_id: 'custom', label: '我的短片', selected: true }],
    });
    expect(request).toEqual({
      expected_version: 0, preset: 'AUDIO',
      values: [{ intent_id: 'custom', label: '我的短片', selected: true }],
    });
  });

  it('rejects the GET-only custom marker, a note field and an unknown intent before it is sent', () => {
    const cases: unknown[] = [
      { expected_version: 0, values: [{ intent_id: 'custom', label: '我的短片', selected: true, custom: true }] },
      { expected_version: 0, values: [], note: '这句话没有所有者字段' },
      { expected_version: 0, values: [{ intent_id: 'unknown_intent', label: 'x', selected: true }] },
      { expected_version: 0, values: [{ intent_id: 'custom', label: '', selected: true }] },
      { expected_version: -1, values: [] },
      { expected_version: null, values: [] },
      { values: [] },
    ];
    for (const candidate of cases) {
      expect(refusalOf(() => studioIntentRequest(candidate)).problem.code).toBe('STUDIO_ENTRY_RESPONSE_INVALID');
    }
  });
});
