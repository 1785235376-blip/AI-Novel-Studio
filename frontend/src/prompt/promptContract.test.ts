import { describe, expect, it } from 'vitest';

import { ApiError } from '../api';
import { promptBody, promptEntry, promptInvalid, promptLibrary, promptReceipt } from './promptContract';
import { readPromptConflict } from './promptClient';

const body = (over: Record<string, unknown> = {}) => ({
  state: 'COMPLETE', value: '一个瘦高的男人站在雨里\n第二行 🙂\n', digest: 'a'.repeat(64),
  digest_of: 'ORIGINAL_BYTES', truncated: false, decodable: true, body_validated: true,
  tail_unverified: false, original_length: 42, preview_length: 42, limit: 65536, fetch: 'INCLUDED',
  ...over,
});

const field = (name: string, value: unknown, authored = true) =>
  ({ field: name, label: name, value: authored ? value : 'UNKNOWN', authored, state: authored ? 'KNOWN' : 'UNKNOWN' });

const version = (over: Record<string, unknown> = {}) => ({
  asset_id: 'asset-1', revision: 1, asset_version: 2, change_note: '初稿', change_reason: '第一版',
  previous_asset_id: null, redacted: false, available: true, ...over,
});

const entry = (over: Record<string, unknown> = {}) => ({
  contract: 'studio-prompt-library/1', family_id: 'fam-1', head_asset_id: 'asset-1', revision: 1,
  asset_version: 2, purpose: 'IMAGE', origin: 'MANUAL', review_status: 'DRAFT', approved: false,
  redacted: false, body: body(),
  // Real producer shape (__fixtures__/library.json): group-level and row-level
  // verification, and each row carries its kind.
  bindings: {
    characters: [{ kind: 'CHARACTER', id: 'c1', resolution: 'KNOWN', verification: 'INDEX_SUPPLIED' }],
    scenes: [], shots: [], assets: [], verification: 'INDEX_SUPPLIED',
  },
  unresolved_bindings: [], reference_asset_ids: [], output_asset_ids: [], anomalies: [],
  versions: [version()],
  fields: [field('text', '一个瘦高的男人站在雨里\n第二行 🙂\n'), field('negative_prompt', 'UNKNOWN', false),
    field('model_reference', 'flux-1'), field('parameters', {}), field('seed', 'UNKNOWN', false)],
  history_complete: true, read_complete: true, ...over,
});

const library = (over: Record<string, unknown> = {}) => ({
  contract: 'studio-prompt-library/1', entries: [entry()], prompt_count: 1, revision_count: 1,
  malformed: [], malformed_count: 0, conflicted: [], conflicted_count: 0, scanned_assets: 1,
  projected_families: 1, returned: 1, limit: 200, truncated: false, has_more: false,
  total_known: false, read_complete: true, unknown_is_explicit: true, bible_index_supplied: true, ...over,
});

describe('prompt contract', () => {
  it('decodes a complete projection and preserves the authored body exactly', () => {
    const decoded = promptLibrary(library());
    expect(decoded.entries[0].body.value).toBe('一个瘦高的男人站在雨里\n第二行 🙂\n');
    expect(decoded.entries[0].body.state).toBe('COMPLETE');
    expect(decoded.entries[0].headAssetId).toBe('asset-1');
    expect(decoded.promptCount).toBe(1);
    expect(decoded.readComplete).toBe(true);
  });

  it('rejects an unknown key instead of ignoring it', () => {
    expect(() => promptLibrary(library({ surprise: 1 }))).toThrow(ApiError);
    expect(() => promptEntry(entry({ surprise: 1 }))).toThrow(ApiError);
  });

  it('never lets a preview masquerade as the whole body', () => {
    const truncated = promptEntry(entry({
      body: body({ state: 'TRUNCATED', value: '一个瘦高的男人', truncated: true,
        body_validated: false, tail_unverified: true, original_length: 99999, preview_length: 21 }),
    }));
    expect(truncated.body.state).toBe('TRUNCATED');
    expect(truncated.body.truncated).toBe(true);
    expect(truncated.body.value).toBe('一个瘦高的男人');
  });

  it('requires a non-COMPLETE body to carry no text', () => {
    // UNDECODABLE with a value would be the backend quietly redefining the state.
    expect(() => promptBody(body({ state: 'UNDECODABLE', value: 'OK', decodable: false })))
      .toThrow(ApiError);
    expect(() => promptBody(body({ state: 'REDACTED', value: null, digest: null }))).not.toThrow();
  });

  it('keeps UNKNOWN as UNKNOWN and never renders it as an empty author field', () => {
    const decoded = promptEntry(entry());
    const negative = decoded.fields.find(row => row.field === 'negative_prompt')!;
    expect(negative.authored).toBe(false);
    expect(negative.state).toBe('UNKNOWN');
    expect(negative.value).toBe('UNKNOWN');
    // A field claiming not-authored but carrying a value is a contract violation.
    expect(() => promptEntry(entry({
      fields: [{ field: 'negative_prompt', label: 'x', value: '', authored: false, state: 'UNKNOWN' }],
    }))).toThrow(ApiError);
  });

  it('requires the counts and the list to agree', () => {
    expect(() => promptLibrary(library({ prompt_count: 2 }))).toThrow(ApiError);
    expect(() => promptLibrary(library({ projected_families: 0 }))).toThrow(ApiError);
  });

  it('surfaces conflicted revisions separately and reports incomplete reads', () => {
    const decoded = promptLibrary(library({
      conflicted: [{ asset_id: 'asset-9', family_id: 'fam-1', revision: 2, request_id: 'req-9' }],
      conflicted_count: 1,
      entries: [entry({ history_complete: false, read_complete: false })],
      truncated: true, has_more: true, read_complete: false,
    }));
    expect(decoded.conflictedCount).toBe(1);
    expect(decoded.entries[0].historyComplete).toBe(false);
    expect(decoded.readComplete).toBe(false);
    expect(decoded.hasMore).toBe(true);
  });

  it('exposes a deleted or unavailable revision as unavailable, not as missing history', () => {
    const decoded = promptEntry(entry({
      versions: [version(), version({ asset_id: 'asset-2', revision: 2, previous_asset_id: 'asset-1', available: false })],
      anomalies: [{ kind: 'REVISION_UNAVAILABLE', asset_id: 'asset-2' }],
      history_complete: false,
      revision: 2, head_asset_id: 'asset-2',
    }));
    expect(decoded.versions[1].available).toBe(false);
    expect(decoded.anomalies[0].kind).toBe('REVISION_UNAVAILABLE');
    expect(decoded.historyComplete).toBe(false);
  });

  it('decodes the write receipt, whose asset_id is not the library field', () => {
    const receipt = promptReceipt({
      family_id: 'fam-1', asset_id: 'asset-1', revision: 1, asset_version: 2,
      text_digest: 'b'.repeat(64), idempotent_replay: false, previous_asset_id: null,
      payload_digest: 'c'.repeat(64),
    });
    expect(receipt.assetId).toBe('asset-1');
    expect(receipt.idempotentReplay).toBe(false);
    expect(promptInvalid).toBeTypeOf('function');
  });
});

describe('conflict decoding (R3-W whitelist only)', () => {
  const conflict = (details: unknown) => new ApiError({
    status: 409, code: 'EXPERIMENTAL_VERSION_CONFLICT', message: 'x', details,
  });

  it('recognises the whitelisted prompt conflict codes', () => {
    expect(readPromptConflict(conflict({
      code: 'PROMPT_REVISION_STALE', family_id: 'fam-1', expected_revision: 1,
      current_revision: 2, retryable: true,
    }))).toEqual({
      code: 'PROMPT_REVISION_STALE', familyId: 'fam-1', revision: null,
      expectedRevision: 1, currentRevision: 2, retryable: true,
    });
  });

  it('ignores a non-prompt 409 so other APIs keep their meaning', () => {
    expect(readPromptConflict(conflict({ code: 'EXPERIMENTAL_VERSION_CONFLICT', version: 3 }))).toBeNull();
    expect(readPromptConflict(conflict({}))).toBeNull();
    expect(readPromptConflict(new Error('nope'))).toBeNull();
  });

  it('treats absent whitelist fields as unknown rather than guessing', () => {
    const decoded = readPromptConflict(conflict({ code: 'PROMPT_REQUEST_ID_REUSED' }))!;
    expect(decoded.familyId).toBeNull();
    expect(decoded.currentRevision).toBeNull();
    expect(decoded.retryable).toBe(false);
  });
});
