import { describe, expect, it, vi } from 'vitest';
import storyboardFixture from './fixtures/phase4.file-api-storyboard.json';
import imageFixture from './fixtures/phase4.file-api-image-request.json';
import timelineFixture from './fixtures/phase4.file-api-timeline-draft.json';
import adviceFixture from './fixtures/phase4.file-api-director-advice.json';
import planningFixture from './fixtures/productionGraph.planning-run.json';
import { checkedCreativeShot, checkedPlanningProjection } from './studioProductionGraphContract';
import { checkedDirectorAdvice, checkedStoryboardImageRequest, checkedStoryboardReceipt, checkedStoryboardTimeline, type ShotPin } from './studioStoryboardContract';
import { createStoryboardClient } from './studioStoryboardClient';

// These new captures contain synthetic content produced by the mounted API tests.
// A receipt is evidence of its contract, never evidence of real model acceptance.
const copy = <T,>(value: T): T => structuredClone(value);
const record = (value: unknown) => value as Record<string, unknown>;
const receipt = () => checkedStoryboardReceipt(copy(storyboardFixture));
const imagePin = (): ShotPin => copy(imageFixture.shot_pin);
const nextReceipt = () => ({ ...copy(storyboardFixture), document_snapshot: { ...storyboardFixture.document_snapshot, version: storyboardFixture.document_snapshot.version + 1 } });

describe('Mounted Storyboard receipts keep original document, shot and image version pins', () => {
  it('decodes the real synthetic receipt with optional previous/next continuity', () => {
    const result = receipt();
    expect(result.document_snapshot).toEqual(storyboardFixture.document_snapshot);
    expect(result.shots[0]).toEqual(storyboardFixture.shots[0]);
    expect(result.shots[0].shot.continuity?.next_shot_id).toBe('shot-2');
    expect(result.shots[1].shot.continuity?.previous_shot_id).toBe('shot-1');
    expect(result.approved).toBe(true); expect(result.model_called).toBe(false);
    expect(result.product_acceptance).toBe('LOCAL_REQUIRED');
  });
  it.each([
    ['automatic model claim', (r: Record<string, unknown>) => { r.model_called = true; }],
    ['acceptance claim', (r: Record<string, unknown>) => { r.product_acceptance = 'PASS'; }],
    ['unknown field', (r: Record<string, unknown>) => { r.execute = 'command'; }],
    ['document version', (r: Record<string, unknown>) => { record(r.document_snapshot).version = 0; }],
    ['document digest', (r: Record<string, unknown>) => { record(r.document_snapshot).digest = 'A'.repeat(64); }],
    ['shot identity', (r: Record<string, unknown>) => { record((r.shots as unknown[])[0]).shot_id = 'other-shot'; }],
    ['shot history version', (r: Record<string, unknown>) => { record((r.shots as unknown[])[0]).shot_version = 0; }],
    ['image version', (r: Record<string, unknown>) => { record(record((r.shots as unknown[])[0]).image_asset).version = 0; }],
    ['image kind', (r: Record<string, unknown>) => { record(record((r.shots as unknown[])[0]).image_asset).kind = 'video'; }],
    ['unknown continuity', (r: Record<string, unknown>) => { record(record(record((r.shots as unknown[])[0]).shot).continuity).next_shot_id = 'missing'; }],
  ])('rejects malformed %s', (_name, mutate) => {
    const value = record(copy(storyboardFixture)); mutate(value);
    expect(() => checkedStoryboardReceipt(value)).toThrow();
  });
  it('rejects another requested document, repeated shots and reordered shot numbers', () => {
    expect(() => checkedStoryboardReceipt(storyboardFixture, 'another-document')).toThrow();
    const repeated = copy(storyboardFixture); repeated.shots[1] = copy(repeated.shots[0]);
    expect(() => checkedStoryboardReceipt(repeated)).toThrow();
    const reordered = copy(storyboardFixture); reordered.shots.reverse();
    expect(() => checkedStoryboardReceipt(reordered)).toThrow();
  });
  it.each(['characters', 'outfit', 'environment', 'camera'] as const)('bounds continuity %s at 4000 characters', key => {
    const shot = copy(storyboardFixture.shots[0].shot); shot.continuity[key] = 'a'.repeat(4000);
    expect(() => checkedCreativeShot(shot)).not.toThrow(); shot.continuity[key] += 'a';
    expect(() => checkedCreativeShot(shot)).toThrow();
  });
  it('allows omitted or null neighbor pins but rejects self references and duplicate note IDs', () => {
    const shot = record(copy(storyboardFixture.shots[0].shot)), continuity = record(shot.continuity);
    delete continuity.next_shot_id; continuity.previous_shot_id = null;
    shot.director_note_ids = ['note-a', 'note-b']; expect(() => checkedCreativeShot(shot)).not.toThrow();
    continuity.previous_shot_id = shot.id; expect(() => checkedCreativeShot(shot)).toThrow();
    continuity.previous_shot_id = null; shot.director_note_ids = ['note-a', 'note-a'];
    expect(() => checkedCreativeShot(shot)).toThrow();
  });
});

describe('Director advice remains read only and respects the original content bounds', () => {
  it('decodes actual advice without claiming inference or automatic changes', () => {
    expect(checkedDirectorAdvice(copy(adviceFixture), adviceFixture.document_snapshot.id)).toEqual(adviceFixture);
  });
  it.each(['advice_only', 'automatic_apply', 'model_called'] as const)('rejects a changed %s gate', key => {
    const value = copy(adviceFixture); value[key] = !value[key];
    expect(() => checkedDirectorAdvice(value, value.document_snapshot.id)).toThrow();
  });
  it.each([['lighting', 4000], ['material', 4000], ['color', 2000], ['style', 2000]] as const)('checks visual %s limit %s', (key, limit) => {
    const value = copy(adviceFixture); value.notes[0].visual_style[key] = 'x'.repeat(limit);
    expect(() => checkedDirectorAdvice(value, value.document_snapshot.id)).not.toThrow(); value.notes[0].visual_style[key] += 'x';
    expect(() => checkedDirectorAdvice(value, value.document_snapshot.id)).toThrow();
  });
  it('bounds transition at 2000 and rejects duplicate notes or another document', () => {
    const value = copy(adviceFixture); value.notes[0].rhythm.transition = 'x'.repeat(2000);
    expect(() => checkedDirectorAdvice(value, value.document_snapshot.id)).not.toThrow();
    value.notes[0].rhythm.transition += 'x'; expect(() => checkedDirectorAdvice(value, value.document_snapshot.id)).toThrow();
    expect(() => checkedDirectorAdvice(adviceFixture, 'foreign')).toThrow();
    const duplicate = copy(adviceFixture); duplicate.notes.push(copy(duplicate.notes[0]));
    expect(() => checkedDirectorAdvice(duplicate, duplicate.document_snapshot.id)).toThrow();
  });
  it.each([['lighting', 4000], ['color_palette', 2000], ['material', 4000], ['transition', 2000]] as const)('decodes saved DirectorNote %s to its exact backend bound', (key, limit) => {
    const projection = copy(planningFixture.run.node_states.director.output.direction), note = record(projection.content.director_notes[0]);
    note[key] = 'x'.repeat(limit); expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).not.toThrow();
    note[key] += 'x'; expect(() => checkedPlanningProjection(projection, 'DIRECTOR')).toThrow();
  });
  it('preserves legacy Scene.characters duplicates while new Shot characters remain distinct', () => {
    const projection = copy(planningFixture.run.node_states.director.output.direction);
    projection.content.scenes[0].characters = ['visitor', 'visitor'];
    expect(checkedPlanningProjection(projection, 'DIRECTOR').content.scenes[0].characters).toEqual(['visitor', 'visitor']);
    const shot = { ...copy(storyboardFixture.shots[0].shot), characters: ['visitor', 'visitor'] };
    expect(() => checkedCreativeShot(shot)).toThrow();
  });
});

describe('Storyboard preparation binds reviewed history without automatic dispatch', () => {
  it('accepts the actual image preparation and removes unset legacy parameters', () => {
    const result = checkedStoryboardImageRequest(copy(imageFixture), imagePin());
    expect(result.command.parameters).toEqual({ width: 64, height: 64 });
    expect(result.command.source_snapshots[0]).toMatchObject({ ...imagePin().document_snapshot, kind: 'CREATIVE_DOCUMENT', reference_only: true });
    expect(result.automatic_dispatch).toBe(false); expect(result.output_policy).toBe('PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW');
  });
  it.each([
    ['document history', (r: Record<string, unknown>) => { record(record(r.shot_pin).document_snapshot).version = 2; }],
    ['shot history', (r: Record<string, unknown>) => { record(r.shot_pin).shot_digest = 'b'.repeat(64); }],
    ['source history', (r: Record<string, unknown>) => { record((record(r.command).source_snapshots as unknown[])[0]).digest = 'b'.repeat(64); }],
    ['source role', (r: Record<string, unknown>) => { record((record(r.command).source_snapshots as unknown[])[0]).reference_only = false; }],
    ['cloud dispatch', (r: Record<string, unknown>) => { record(r.command).allow_cloud = true; }],
    ['automatic dispatch', (r: Record<string, unknown>) => { r.automatic_dispatch = true; }],
    ['unknown parameter', (r: Record<string, unknown>) => { record(record(r.command).parameters).workflow = {}; }],
  ])('rejects changed %s', (_name, mutate) => {
    const value = record(copy(imageFixture)); mutate(value); expect(() => checkedStoryboardImageRequest(value, imagePin())).toThrow();
  });
  it('accepts actual timeline origin independently of object key order', () => {
    const result = checkedStoryboardTimeline(copy(timelineFixture), timelineFixture.timeline.novel_id, null);
    expect(result.timeline.version).toBe(1); expect(result.rendered).toBe(false); expect(result.automatic_dispatch).toBe(false);
    expect(result.storyboard_origin.shots).toEqual(timelineFixture.storyboard_origin.shots);
  });
  it('rejects an altered timeline version, clip mapping, scope and render claim', () => {
    const version = copy(timelineFixture); version.storyboard_origin.timeline_snapshot.version++;
    expect(() => checkedStoryboardTimeline(version, version.timeline.novel_id, null)).toThrow();
    const mapping = copy(timelineFixture); mapping.storyboard_origin.shots[0].clip_id = 'wrong';
    expect(() => checkedStoryboardTimeline(mapping, mapping.timeline.novel_id, null)).toThrow();
    const rendered = { ...copy(timelineFixture), rendered: true };
    expect(() => checkedStoryboardTimeline(rendered, rendered.timeline.novel_id, null)).toThrow();
    expect(() => checkedStoryboardTimeline(timelineFixture, 'foreign', null)).toThrow();
  });
});

describe('Original scoped Storyboard client sends explicit CAS actions', () => {
  it('keeps read endpoints read only and passes cancellation signals', async () => {
    const request = vi.fn().mockResolvedValueOnce(copy(storyboardFixture)).mockResolvedValueOnce(copy(adviceFixture)), signal = new AbortController().signal;
    const client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    await client.storyboardGet(storyboardFixture.document_snapshot.id, signal); await client.directorAdvice(adviceFixture.document_snapshot.id, signal);
    expect(request.mock.calls).toEqual([
      [`/api/synthetic/documents/${storyboardFixture.document_snapshot.id}/storyboard`, 'GET', undefined, signal],
      [`/api/synthetic/documents/${adviceFixture.document_snapshot.id}/director-advice`, 'GET', undefined, signal],
    ]);
  });
  it('binds exact image and shot history and requires one document version advance', async () => {
    const current = receipt(), shot = current.shots[0], request = vi.fn().mockResolvedValueOnce({ ...nextReceipt(), approved: false }).mockResolvedValueOnce(copy(storyboardFixture));
    const client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    await client.storyboardBindImage(current, shot, shot.image_asset!);
    expect(request.mock.calls[0]).toEqual([`/api/synthetic/documents/${current.document_snapshot.id}/shots/${shot.shot_id}/image-binding`, 'POST',
      { expected_version: current.document_snapshot.version, shot_version: shot.shot_version, shot_digest: shot.shot_digest, asset: shot.image_asset }]);
    await expect(client.storyboardApprove(current)).rejects.toBeTruthy();
    expect(request.mock.calls[1][2]).toEqual({ expected_version: current.document_snapshot.version, reviewed_content_digest: current.content_digest });
  });
  it('prepares an image command at the pinned older document without dispatching jobs', async () => {
    const current = receipt(); current.document_snapshot = imagePin().document_snapshot;
    const request = vi.fn().mockResolvedValue(copy(imageFixture)), client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    const result = await client.storyboardImageRequest(current, current.shots[0], 'm5.image.t2i', imageFixture.command.provider_id, imageFixture.command.model_id, imageFixture.command.request_id, { width: 64, height: 64 });
    expect(request).toHaveBeenCalledTimes(1); expect(request.mock.calls[0][0]).toMatch(/\/image-request$/);
    expect(request.mock.calls[0][2]).toMatchObject({ expected_version: 1, shot_version: 1, shot_digest: current.shots[0].shot_digest });
    expect(result.automatic_dispatch).toBe(false);
  });
  it.each(['provider_id', 'model_id', 'request_id', 'operation_id'] as const)('rejects an image preparation for another requested %s', async key => {
    const current = receipt(); current.document_snapshot = imagePin().document_snapshot;
    const response = copy(imageFixture); response.command[key] = key === 'operation_id' ? 'm5.image.i2i' : 'another-request';
    const request = vi.fn().mockResolvedValue(response), client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    await expect(client.storyboardImageRequest(current, current.shots[0], 'm5.image.t2i', imageFixture.command.provider_id, imageFixture.command.model_id, imageFixture.command.request_id, { width: 64, height: 64 })).rejects.toBeTruthy();
  });
  it.each(['approved', 'content_digest'] as const)('rejects an approval response with changed %s', async key => {
    const response = nextReceipt(); if (key === 'approved') response.approved = false; else response.content_digest = 'c'.repeat(64);
    const request = vi.fn().mockResolvedValue(response), client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    await expect(client.storyboardApprove(receipt())).rejects.toBeTruthy();
  });
  it('rejects a binding response that advances the document but binds another image version', async () => {
    const current = receipt(), response = { ...nextReceipt(), approved: false }; response.shots[0].image_asset.version++;
    const request = vi.fn().mockResolvedValue(response), client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    await expect(client.storyboardBindImage(current, current.shots[0], current.shots[0].image_asset!)).rejects.toBeTruthy();
  });
  it('creates only an unrendered timeline draft and rejects a changed shot history receipt', async () => {
    const request = vi.fn().mockResolvedValueOnce(copy(timelineFixture)), current = receipt();
    const client = createStoryboardClient(timelineFixture.timeline.novel_id, '/api/synthetic', null, request);
    expect((await client.storyboardTimelineDraft(current, ['shot-1', 'shot-2'], 'Synthetic draft')).rendered).toBe(false);
    expect(request.mock.calls[0][2]).toEqual({ expected_version: 4, reviewed_content_digest: current.content_digest, shot_ids: ['shot-1', 'shot-2'], title: 'Synthetic draft', width: 1280, height: 720, fps: 24 });
    const altered = copy(timelineFixture); altered.storyboard_origin.shots[0].shot_digest = 'c'.repeat(64); altered.timeline.storyboard_origin.shots[0].shot_digest = 'c'.repeat(64);
    request.mockResolvedValueOnce(altered); await expect(client.storyboardTimelineDraft(current, ['shot-1', 'shot-2'], 'Synthetic draft')).rejects.toBeTruthy();
  });
});
