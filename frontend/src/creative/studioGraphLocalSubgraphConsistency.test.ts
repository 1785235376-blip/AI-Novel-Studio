import { createHash, webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import actual from './fixtures/localSubgraph.file-api.json';
import { createStudioGraphClient } from './studioGraphClient';

beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const bound = (read: () => unknown) => createStudioGraphClient(actual.project, {}, {
  json: async <T,>(url: string): Promise<T> => (url.endsWith('/preflight') || url.includes('/graph-runs/') || url.endsWith('/runs') ? read() : structuredClone(actual.parent)) as T,
});
const sha = (text: string) => createHash('sha256').update(text, 'utf8').digest('hex');

it('binds preflight call identities, source version/digests and interface to the observed saved parent pin', async () => {
  const positive = bound(() => actual.preflight); await positive.get(actual.parent.id);
  expect((await positive.preflight(actual.parent.id, { expected_version: 1, target_node_ids: [] })).executable).toBe(true);
  const mutations = [
    (value: typeof actual.preflight) => { value.local_subgraph_bindings.call.source.version++; },
    (value: typeof actual.preflight) => { value.local_subgraph_bindings.call.source.id = 'other-child'; },
    (value: typeof actual.preflight) => { value.local_subgraph_bindings.call.source.definition_digest = 'a'.repeat(64); },
    (value: typeof actual.preflight) => { value.local_subgraph_bindings.call.source.execution_digest = 'b'.repeat(64); },
    (value: typeof actual.preflight) => { value.local_subgraph_bindings.call.interface.input.node_id = 'other-entry'; },
    (value: typeof actual.preflight) => { value.local_subgraph_bindings.call.interface.output.node_id = 'other-exit'; },
    (value: typeof actual.preflight) => { Object.assign(value, { local_subgraph_bindings: {} }); },
    (value: typeof actual.preflight) => { const call = { ...value.local_subgraph_bindings.call, call_node_id: 'other-call' }; Object.assign(value, { local_subgraph_bindings: { 'other-call': call } }); },
  ];
  for (const mutate of mutations) {
    const malformed = structuredClone(actual.preflight); mutate(malformed);
    const client = bound(() => malformed); await client.get(actual.parent.id);
    await expect(client.preflight(actual.parent.id, { expected_version: 1, target_node_ids: [] })).rejects.toThrow();
  }
});

it('checks actual completed output and reconstructable input hashes across GET/list/action, while retaining masked redaction', async () => {
  const positive = bound(() => actual.waiting); await positive.get(actual.parent.id);
  expect((await positive.getRun(actual.waiting.id)).review?.draft.origin).toBe('USER_SUPPLIED');
  const mutations = [
    (value: typeof actual.waiting) => { value.local_subgraph_runtime.receipts.call.output_digest = 'a'.repeat(64); },
    (value: typeof actual.waiting) => { value.local_subgraph_runtime.receipts.call.input_digest = 'b'.repeat(64); },
    (value: typeof actual.waiting) => { value.node_states.call.output.draft.text += ' altered'; },
    (value: typeof actual.waiting) => { value.node_states.input.output.text += ' altered'; },
  ];
  for (const mutate of mutations) {
    const malformed = structuredClone(actual.waiting); mutate(malformed);
    const client = bound(() => malformed); await client.get(actual.parent.id);
    await expect(client.getRun(malformed.id)).rejects.toThrow();
  }
  const bad = structuredClone(actual.waiting); bad.local_subgraph_runtime.receipts.call.output_digest = 'a'.repeat(64);
  const listed = bound(() => ({ items: [bad] })); await listed.get(actual.parent.id);
  await expect(listed.runs(actual.parent.id)).rejects.toThrow();
  const action = bound(() => bad); await action.get(actual.parent.id);
  await expect(action.action(bad.id, 'execute', { expected_version: 1 })).rejects.toThrow();
  // Invalid digests must not mint a remembered run-to-graph binding.
  const unseen = { ...structuredClone(actual.waiting), graph_id: 'other-unobserved-graph' };
  let reply: unknown = bad; const notRemembered = bound(() => reply); await notRemembered.get(actual.parent.id);
  await expect(notRemembered.getRun(bad.id)).rejects.toThrow(); reply = unseen;
  expect((await notRemembered.getRun(unseen.id)).graph_id).toBe(unseen.graph_id);
  const masked = structuredClone(actual.masked_run);
  Object.assign(masked.local_subgraph_runtime, { bindings: actual.waiting.local_subgraph_runtime.bindings,
    receipts: { call: { output_digest: 'malformed private material' } } });
  const redacted = await bound(() => masked).getRun(masked.id);
  expect(redacted.review).toBeNull(); expect(redacted.local_subgraph_runtime?.receipts).toEqual({});
  expect(Object.values(redacted.node_states).every(state => state.output === null)).toBe(true);
});

it('uses canonical UTF-8 plan bytes and retires a hash completion after the observed saved owner changes', async () => {
  const unicode = structuredClone(actual.waiting), text = '中文😀\n第二行 "引号" \u2028';
  const draft = { text, origin: 'USER_SUPPLIED', plan: [{ sequence: 1, beat: text }] };
  unicode.node_states.input.output.text = text; unicode.node_states.call.output.draft = draft;
  unicode.review.draft = structuredClone(draft);
  const canonicalDraft = JSON.stringify({ origin: 'USER_SUPPLIED', plan: [{ beat: text, sequence: 1 }], text });
  unicode.local_subgraph_runtime.receipts.call.input_digest = sha(JSON.stringify({ text }));
  unicode.local_subgraph_runtime.receipts.call.output_digest = sha(`{"draft":${canonicalDraft}}`);
  unicode.review.output_digest = sha(canonicalDraft);
  const positive = bound(() => unicode); await positive.get(actual.parent.id);
  expect((await positive.getRun(unicode.id)).node_states.call.output?.draft?.text).toBe(text);
  const client = bound(() => actual.waiting); await client.get(actual.parent.id);
  let release!: () => void, entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const started = new Promise<void>(resolve => { entered = resolve; });
  const original = webcrypto.subtle.digest.bind(webcrypto.subtle);
  vi.spyOn(webcrypto.subtle, 'digest').mockImplementationOnce(async (...args) => { entered(); await gate; return original(...args); });
  const late = client.getRun(actual.waiting.id); await started;
  await client.get(actual.parent.id); release();
  await expect(late).rejects.toThrow();
});
