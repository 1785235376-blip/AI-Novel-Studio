/**
 * R3-U3 §2 —— 生产者/消费者契约核验。
 *
 * 这些断言消费的是**真实后端**产出的 JSON（由
 * `scripts/capture_prompt_contract_fixture.py` 在隔离 File 环境里重新采集），
 * 不是手写的 TS 假对象。样本正文是合成的测试文本，不含任何用户内容。
 *
 * 这样解码器与生产者一旦不一致，就是这里的失败，而不是浏览器里的空白页。
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { ApiError } from '../api';
import { promptEntry, promptLibrary, promptRevisionBody } from './promptContract';
import {
  BINDING_VERIFICATIONS, PROMPT_CONTRACT, PROMPT_DETAIL_CONTRACT,
  PROMPT_REVISION_BODY_CONTRACT,
} from './promptTypes';

const fixture = (name: string): unknown => JSON.parse(readFileSync(
  fileURLToPath(new URL(`./__fixtures__/${name}`, import.meta.url)), 'utf-8')) as unknown;

describe('real producer output decodes (R3-U3 §2.1)', () => {
  it('decodes the real library envelope, including the service-added fields', () => {
    const raw = fixture('library.json') as Record<string, unknown>;
    // Guard the guard: these are the producer's real keys, not ours.
    for (const key of ['required_fields', 'purposes', 'origins', 'binding_kinds',
      'project_id', 'scope', 'generated_at', 'asset_owner', 'bible_owner']) {
      expect(Object.hasOwn(raw, key), `producer no longer emits ${key}`).toBe(true);
    }
    const decoded = promptLibrary(raw);
    expect(decoded.promptCount).toBe(1);
    expect(decoded.entries).toHaveLength(1);
    expect(decoded.entries[0].familyId).toBeTruthy();
    expect(decoded.readComplete).toBe(true);
  });

  it('decodes the real empty-library envelope', () => {
    const decoded = promptLibrary(fixture('empty-library.json'));
    expect(decoded.entries).toEqual([]);
    expect(decoded.promptCount).toBe(0);
    expect(decoded.revisionCount).toBe(0);
    expect(decoded.conflictedCount).toBe(0);
  });

  it('decodes the real detail envelope, which carries a different contract and more keys', () => {
    const raw = fixture('detail.json') as Record<string, unknown>;
    expect(raw.contract).toBe(PROMPT_DETAIL_CONTRACT);
    for (const key of ['project_id', 'scope', 'generated_at', 'scan_truncated']) {
      expect(Object.hasOwn(raw, key), `detail no longer emits ${key}`).toBe(true);
    }
    const decoded = promptEntry(raw);
    expect(decoded.revision).toBeGreaterThanOrEqual(1);
    expect(decoded.versions.length).toBeGreaterThanOrEqual(2);
    expect(decoded.historyComplete).toBe(true);
  });

  it('uses the producer contract literals, and library and detail are distinct', () => {
    expect(PROMPT_CONTRACT).toBe('studio-prompt-library/1');
    expect(PROMPT_DETAIL_CONTRACT).toBe('studio-prompt-detail/1');
    expect(PROMPT_CONTRACT).not.toBe(PROMPT_DETAIL_CONTRACT);
    expect((fixture('library.json') as Record<string, unknown>).contract).toBe(PROMPT_CONTRACT);
    expect(PROMPT_REVISION_BODY_CONTRACT).toBe('prompt-revision-body/1');
    expect((fixture('revision-1-body.json') as Record<string, unknown>).contract)
      .toBe(PROMPT_REVISION_BODY_CONTRACT);
  });

  it('keeps rejecting an unknown key and an unknown contract', () => {
    const raw = fixture('library.json') as Record<string, unknown>;
    expect(() => promptLibrary({ ...raw, invented_field: 1 })).toThrow(ApiError);
    expect(() => promptLibrary({ ...raw, contract: 'prompt-library/1' })).toThrow(ApiError);
    expect(() => promptLibrary({ ...raw, contract: 'studio-prompt-library/2' })).toThrow(ApiError);
  });

  it('rejects out-of-range and type-confused values', () => {
    const raw = fixture('library.json') as Record<string, unknown>;
    expect(() => promptLibrary({ ...raw, prompt_count: 99 })).toThrow(ApiError);
    expect(() => promptLibrary({ ...raw, truncated: 'no' })).toThrow(ApiError);
    expect(() => promptLibrary({ ...raw, entries: 'nope' })).toThrow(ApiError);
  });
});

describe('real bindings verification (R3-U3 §2.2)', () => {
  it('decodes kind and verification, and never upgrades INDEX_SUPPLIED to approval', () => {
    const decoded = promptLibrary(fixture('library.json'));
    const bindings = decoded.entries[0].bindings;
    expect(bindings.verification).toBe('INDEX_SUPPLIED');
    expect(BINDING_VERIFICATIONS).toContain(bindings.verification);
    const character = bindings.characters[0];
    expect(character.kind).toBe('CHARACTER');
    expect(character.resolution).toBe('KNOWN');
    // "the index had it" is all this says. It is not a review or a save-time check.
    expect(character.verification).toBe('INDEX_SUPPLIED');
    expect(Object.keys(bindings)).toContain('verification');
  });

  it('rejects an unknown verification source instead of trusting it', () => {
    const raw = fixture('library.json') as Record<string, unknown>;
    const entries = structuredClone(raw.entries) as Record<string, unknown>[];
    (entries[0].bindings as Record<string, unknown>).verification = 'APPROVED_BY_AI';
    expect(() => promptLibrary({ ...raw, entries })).toThrow(ApiError);
  });
});

describe('real revision bodies enable a true text diff (R3-U3 §3.3)', () => {
  it('decodes both real revision bodies as verified COMPLETE text', () => {
    const first = promptRevisionBody(fixture('revision-1-body.json'));
    const second = promptRevisionBody(fixture('revision-2-body.json'));
    for (const body of [first, second]) {
      expect(body.state).toBe('COMPLETE');
      expect(body.verified).toBe(true);
      expect(body.available).toBe(true);
      expect(body.readComplete).toBe(true);
      expect(body.digestOf).toBe('ORIGINAL_BYTES');
      expect(typeof body.value).toBe('string');
    }
    expect(first.assetId).not.toBe(second.assetId);
    expect(first.revision).not.toBe(second.revision);
    // The real texts differ, so a diff is meaningful rather than a restatement of metadata.
    expect(first.value).not.toBe(second.value);
    expect(first.digest).not.toBe(second.digest);
    expect(first.familyId).toBe(second.familyId);
  });

  it('rejects a body that claims verification without a digest', () => {
    const raw = fixture('revision-1-body.json') as Record<string, unknown>;
    expect(() => promptRevisionBody({ ...raw, digest: null })).toThrow(ApiError);
  });

  it('rejects a non-COMPLETE state that still carries text', () => {
    const raw = fixture('revision-1-body.json') as Record<string, unknown>;
    expect(() => promptRevisionBody({ ...raw, state: 'REDACTED' })).toThrow(ApiError);
    expect(() => promptRevisionBody({ ...raw, state: 'UNAVAILABLE' })).toThrow(ApiError);
    // A truncated preview is legitimate and keeps its (preview) text.
    const preview = promptRevisionBody({
      ...raw, state: 'TRUNCATED', truncated: true, verified: false,
    });
    expect(preview.state).toBe('TRUNCATED');
    expect(preview.truncated).toBe(true);
  });
});
