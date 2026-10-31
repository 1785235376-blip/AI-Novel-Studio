import { expect, it, vi } from 'vitest';
import captured from './directorScreenplayWire.testFixture.json';
import { checkedDirectorPendingReceipt, createDirectorModelClient } from './directorModelClient';
import { multiShotFixture } from './directorScreenplayMultiShot.testFixtures';
const p = captured.preview.receipt, pin = { id: p.source_document_id, version: p.source_version, digest: p.source_digest };
const input = { expected_version: p.version - 1, route_id: p.route_id };
function setup(...responses: unknown[]) {
  const json = vi.fn(); responses.forEach(value => json.mockResolvedValueOnce(value));
  return { json, client: createDirectorModelClient(captured.preview.project_id, { json }, undefined, 'SCREENPLAY') };
}
it('leaves omitted planning mode byte-for-byte V2 and requires explicit V3 opt-in', async () => {
  const fixture = multiShotFixture(), { client, json } = setup(captured.preview, fixture.preview);
  expect(await client.preview(p.proposal_id, pin, input)).toEqual(captured.preview.receipt);
  expect(json.mock.calls[0][2]).toEqual({ ...input, allow_synthetic: false, max_output_tokens: 512, temperature: 0 });
  expect(await client.preview(p.proposal_id, pin, { ...input, planning_mode: 'MULTI_SHOT_V1' })).toEqual(fixture.preview.receipt);
  expect(json.mock.calls[1][2]).toEqual({ ...json.mock.calls[0][2], planning_mode: 'MULTI_SHOT_V1' });
  expect(json.mock.calls.every(([url]) => url.endsWith('/model-v2/preview'))).toBe(true);
});
it('keeps four selected candidates across two scenes through dispatch, prepare, human edit, and review', async () => {
  const fixture = multiShotFixture(), { client, json } = setup(fixture.preview, fixture.completed_status, fixture.pending, fixture.adopted);
  const preview = await client.preview(p.proposal_id, pin, { ...input, planning_mode: 'MULTI_SHOT_V1' });
  const status = await client.dispatch(p.proposal_id, pin, preview), pending = await client.prepareReview(p.proposal_id, pin, status);
  expect(pending).toEqual(fixture.pending.receipt);
  expect(pending.director_notes.map(note => note.scene_id)).toEqual(['scene-a', 'scene-a', 'scene-b', 'scene-b']);
  expect(pending.provenance.allowed_source_mapping).toHaveLength(6);
  const body = fixture.submitted_review; body.director_notes[0].note = 'Human refinement'; body.director_notes[3].duration_seconds = 12;
  expect(await client.review(p.proposal_id, body, pending)).toEqual(fixture.adopted.receipt);
  expect(json.mock.calls.at(-1)?.[2]).toEqual(body);
  expect(json.mock.calls.every(([url]) => url.includes('/model-v2/'))).toBe(true);
});
it('reads V3 receipts without writes and detaches allowed slots, selected IDs, and nested planning', async () => {
  const fixture = multiShotFixture(), { client, json } = setup(fixture.preview, fixture.pending);
  const preview = await client.readPreview(p.proposal_id, pin), pending = await client.readPending(p.proposal_id, pin);
  preview.allowed_source_mapping![0].note_id = 'local'; pending.provenance.allowed_source_mapping![0].scene_id = 'local';
  pending.provenance.source_mapping[0].note_id = 'local'; pending.director_notes[0].planning!.rationale = 'local';
  expect(fixture.preview.receipt.allowed_source_mapping![0].note_id).toBe('scene-a-candidate-1');
  expect(fixture.pending.receipt.provenance.allowed_source_mapping![0].scene_id).toBe('scene-a');
  expect(fixture.pending.receipt.provenance.source_mapping[0].note_id).toBe('scene-a-candidate-1');
  expect(fixture.pending.receipt.director_notes[0].planning!.rationale).not.toBe('local');
  expect(json.mock.calls.every(([, method, body]) => method === 'GET' && body === undefined)).toBe(true);
});
it.each([null, true, '', 'SCENE_V2', 'MULTI_SHOT_V2'])('rejects invalid opt-in %s before transport', async planning_mode => {
  const { client, json } = setup();
  await expect(client.preview(p.proposal_id, pin, { ...input, planning_mode } as never)).rejects.toThrow();
  expect(json).not.toHaveBeenCalled();
});
it('does not accept screenplay planning opt-in through a storyboard client', async () => {
  const json = vi.fn(), client = createDirectorModelClient(captured.preview.project_id, { json });
  await expect(client.preview(p.proposal_id, pin, { ...input, planning_mode: 'MULTI_SHOT_V1' })).rejects.toThrow();
  expect(json).not.toHaveBeenCalled();
});
it.each(['unsolicited-v3', 'downgraded-v2'])('rejects %s after one request with no retry or fallback', async change => {
  const { client, json } = setup(change === 'unsolicited-v3' ? multiShotFixture().preview : captured.preview);
  await expect(client.preview(p.proposal_id, pin, change === 'unsolicited-v3' ? input : { ...input, planning_mode: 'MULTI_SHOT_V1' })).rejects.toThrow();
  expect(json).toHaveBeenCalledTimes(1);
});
it.each(['missing-mode', 'wrong-mode', 'missing-slots', 'missing-slot', 'duplicate-id', 'duplicate-slot', 'scene-mismatch', 'sequence-mismatch', 'reversed-scenes', 'third-scene', 'private-field', 'stale-source'])('rejects invalid V3 preview %s', async change => {
  const fixture: any = multiShotFixture(), row = fixture.preview.receipt, allowed = row.allowed_source_mapping;
  if (change === 'missing-mode') delete row.planning_mode;
  if (change === 'wrong-mode') row.planning_mode = 'SCENE_V2';
  if (change === 'missing-slots') delete row.allowed_source_mapping;
  if (change === 'missing-slot') allowed.pop();
  if (change === 'duplicate-id') allowed[1].note_id = allowed[0].note_id;
  if (change === 'duplicate-slot') allowed[1].slot = 1;
  if (change === 'scene-mismatch') allowed[1].scene_id = 'scene-c';
  if (change === 'sequence-mismatch') allowed[1].source_sequence++;
  if (change === 'reversed-scenes') row.allowed_source_mapping = [...allowed.slice(3), ...allowed.slice(0, 3)];
  if (change === 'third-scene') allowed.push(...allowed.slice(0, 3).map((r: any) => ({ ...r, note_id: r.note_id + '-third', scene_id: 'scene-c', source_sequence: 10 })));
  if (change === 'private-field') allowed[0].source_shot_id = 'invented';
  if (change === 'stale-source') row.source_version++;
  const { client, json } = setup(fixture.preview); await expect(client.readPreview(p.proposal_id, pin)).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(1);
});
it.each(['output-contract', 'missing-allowed', 'missing-slot', 'duplicate-id', 'unknown-id', 'changed-scene', 'changed-sequence', 'global-gap', 'reversed-slots', 'reversed-scenes', 'missing-scene', 'mixed-mode', 'v2-contract', 'evidence-scene', 'scope', 'source'])('rejects invalid V3 pending %s', async change => {
  const fixture: any = multiShotFixture(), row = fixture.pending.receipt, provenance = row.provenance, mapping = provenance.source_mapping;
  if (change === 'output-contract') provenance.output_contract = 'SCENE_EVIDENCED_CANDIDATES_V1';
  if (change === 'missing-allowed') delete provenance.allowed_source_mapping;
  if (change === 'missing-slot') provenance.allowed_source_mapping.pop();
  if (change === 'duplicate-id') { mapping[1].note_id = mapping[0].note_id; row.director_notes[1].id = mapping[0].note_id; }
  if (change === 'unknown-id') { mapping[0].note_id = 'unknown'; row.director_notes[0].id = 'unknown'; }
  if (change === 'changed-scene') { mapping[0].scene_id = 'foreign'; row.director_notes[0].scene_id = 'foreign'; row.director_notes[0].planning.evidence[0].scene_id = 'foreign'; }
  if (change === 'changed-sequence') mapping[0].source_sequence++;
  if (change === 'global-gap') { mapping[2].number++; row.director_notes[2].number++; }
  if (change === 'reversed-slots') { [mapping[0], mapping[1]] = [mapping[1], mapping[0]]; [row.director_notes[0], row.director_notes[1]] = [row.director_notes[1], row.director_notes[0]]; }
  if (change === 'reversed-scenes') { mapping.reverse(); row.director_notes.reverse(); }
  if (['reversed-slots', 'reversed-scenes'].includes(change)) { mapping.forEach((r: any, i: number) => r.number = i + 1); row.director_notes.forEach((r: any, i: number) => r.number = i + 1); }
  if (change === 'missing-scene') { provenance.source_mapping = mapping.slice(0, 2); row.director_notes = row.director_notes.slice(0, 2); }
  if (change === 'mixed-mode') provenance.source_mode = 'STORYBOARD';
  if (change === 'v2-contract') row.contract = 'DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V2';
  if (change === 'evidence-scene') row.director_notes[0].planning.evidence[0].scene_id = 'scene-b';
  if (change === 'scope') fixture.pending.scope.branch_id = 'foreign';
  if (change === 'source') provenance.source_digest = '0'.repeat(64);
  const { client, json } = setup(fixture.pending); await expect(client.readPending(p.proposal_id, pin)).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(1);
});
it.each(['id', 'scene', 'order', 'number', 'drop', 'add', 'version', 'digest'])('rejects human review %s changes before either write or reconciliation', async change => {
  const fixture = multiShotFixture(), { client, json } = setup();
  const pending = checkedDirectorPendingReceipt(fixture.pending.receipt, p.proposal_id, pin, 'SCREENPLAY'), body = fixture.submitted_review;
  if (change === 'id') body.director_notes[0].id = 'replacement';
  if (change === 'scene') body.director_notes[0].scene_id = 'scene-b';
  if (change === 'order') body.director_notes.reverse();
  if (change === 'number') body.director_notes[0].number = 2;
  if (change === 'drop') body.director_notes.pop();
  if (change === 'add') body.director_notes.push(structuredClone(body.director_notes[0]));
  if (change === 'version') body.expected_version++;
  if (change === 'digest') body.reviewed_output_digest = '0'.repeat(64);
  await expect(client.review(p.proposal_id, body, pending)).rejects.toThrow();
  await expect(client.reconcileReview(p.proposal_id, body, pending)).rejects.toThrow();
  expect(json).not.toHaveBeenCalled();
});
it.each([{ counts: [1] }, { counts: [3] }, { counts: [1, 1] }, { counts: [3, 3] }])('accepts the bounded scene shot counts $counts', async ({ counts }) => {
  const fixture = multiShotFixture(), pending = fixture.pending.receipt;
  const allowed = pending.provenance.allowed_source_mapping!.slice(0, counts.length * 3);
  const selected = allowed.filter((row, index) => row.slot <= counts[Math.floor(index / 3)]);
  pending.provenance.allowed_source_mapping = allowed;
  pending.provenance.source_mapping = selected.map(({ slot: _slot, ...row }, index) => ({ ...row, number: index + 1 }));
  const template = pending.director_notes[0];
  pending.director_notes = selected.map((row, index) => ({ ...structuredClone(template), id: row.note_id, scene_id: row.scene_id, number: index + 1,
    planning: { ...structuredClone(template.planning!), evidence: template.planning!.evidence.map(evidence => ({ ...evidence, scene_id: row.scene_id })) } }));
  const { client } = setup(fixture.pending);
  expect((await client.readPending(p.proposal_id, pin)).director_notes).toHaveLength(counts.reduce((sum, count) => sum + count, 0));
});

it('preserves the legacy V2 generic human-edit contract', async () => {
  const { client, json } = setup(captured.adopted);
  const pending = checkedDirectorPendingReceipt(captured.pending.receipt, p.proposal_id, pin, 'SCREENPLAY');
  const body = structuredClone(captured.submitted_review); body.director_notes[0].id = 'human-authored'; body.director_notes[0].number = 12;
  expect(await client.review(p.proposal_id, body, pending)).toEqual(captured.adopted.receipt);
  expect(json.mock.calls[0][2]).toEqual(body);
});
