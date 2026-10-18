import { expect, it, vi } from 'vitest';
import captured from './directorScreenplayMultiShotWire.testFixture.json';
import { createDirectorModelClient } from './directorModelClient';
import { readVerifiedModelDraft } from './directorModelDraftHandoff';
import { checkedPlanningProjection } from './studioProductionGraphContract';
import { documentInput, type CreativeDocument } from './types';

// Captured from the backend HTTP/restart protocol test. The provider is a local test adapter, not a quality evaluation.
it('decodes captured V3 HTTP receipts and reopens the exact four-shot human-reviewed draft', async () => {
  const p = captured.preview.receipt, pin = { id: p.source_document_id, version: p.source_version, digest: p.source_digest };
  const json = vi.fn().mockResolvedValueOnce(captured.preview).mockResolvedValueOnce(captured.pending)
    .mockResolvedValueOnce(captured.adopted).mockResolvedValueOnce(captured.adopted).mockResolvedValueOnce(captured.adopted);
  const client = createDirectorModelClient(captured.preview.project_id, { json }, undefined, 'SCREENPLAY');
  expect(await client.preview(p.proposal_id, pin, { expected_version: p.version - 1, route_id: p.route_id,
    planning_mode: 'MULTI_SHOT_V1', ...p.parameters })).toEqual(p);
  const pending = await client.readPending(p.proposal_id, pin);
  expect(pending).toEqual(captured.pending.receipt); expect(pending.director_notes).toHaveLength(4);
  expect(new Set(pending.director_notes.map(note => note.scene_id)).size).toBe(2);
  const adopted = await client.review(p.proposal_id, captured.submitted_review, pending);
  expect(adopted).toEqual(captured.adopted.receipt);
  const creative = { export: vi.fn().mockResolvedValue({ document: captured.document, document_digest: adopted.document.digest }) };
  const reopened = await readVerifiedModelDraft(client, creative, adopted, () => {});
  const projection = checkedPlanningProjection({ document_snapshot: reopened.pin, content: documentInput(reopened.document) }, 'DIRECTOR');
  expect(projection.content.director_notes).toEqual(captured.submitted_review.director_notes);
  expect(projection.content.director_notes.map(note => note.scene_id)).toEqual(['first', 'first', 'first', 'second']);
  expect(json.mock.calls.every(([url]) => url.includes('/model-v2/'))).toBe(true);
  expect(json.mock.calls.filter(([, method]) => method === 'POST').map(([url]) => url.split('/').at(-1))).toEqual(['preview', 'review']);
});
it('keeps all four captured derived storyboard shots and their original Director note links renderable', () => {
  const storyboard = captured.storyboard as unknown as CreativeDocument;
  const projection = checkedPlanningProjection({ document_snapshot: { id: storyboard.id, version: storyboard.version, digest: 'a'.repeat(64) }, content: documentInput(storyboard) }, 'STORYBOARD');
  expect(projection.content.shots).toHaveLength(4);
  expect(projection.content.shots.map(shot => shot.director_note_ids)).toEqual(captured.submitted_review.director_notes.map(note => [note.id]));
  expect(projection.content.shots.map(shot => shot.scene_id)).toEqual(['first', 'first', 'first', 'second']);
});
