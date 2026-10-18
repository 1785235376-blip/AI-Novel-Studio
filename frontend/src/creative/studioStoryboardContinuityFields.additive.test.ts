import { describe, expect, it, vi } from 'vitest';
import fixture from './fixtures/phase4.file-api-storyboard.json';
import planning from './fixtures/productionGraph.planning-run.json';
import { checkedCreativeShot, checkedPlanningProjection } from './studioProductionGraphContract';
import { checkedStoryboardReceipt } from './studioStoryboardContract';
import { readStoryboardImageReceipt, type StoryboardImageAccess } from './storyboardImagePreview';
import { newDocument, type CreativeDocument } from './types';

const copy = <T,>(value: T): T => structuredClone(value);
const shot = () => copy(fixture.shots[0].shot) as unknown as Record<string, unknown>;
const continuity = (value: Record<string, unknown>) => value.continuity as Record<string, unknown>;
describe('original optional ShotContinuity time/lighting wire fields', () => {
  it('preserves the exact legacy absent wire shape and explicit nulls', () => {
    const value = shot(), before = JSON.stringify(value);
    expect(JSON.stringify(checkedCreativeShot(value))).toBe(before);
    for (const key of ['time', 'lighting']) expect(Object.hasOwn(checkedCreativeShot(value).continuity!, key)).toBe(false);
    continuity(value).time = null; continuity(value).lighting = null;
    expect(checkedCreativeShot(value).continuity).toEqual(continuity(value));
  });
  it.each(['time', 'lighting'])('matches server string and Unicode bounds for %s', key => {
    for (const text of ['', ' ', 'at dawn\nwith rain', '\u0000\u007f', 'x'.repeat(4000), '🌄'.repeat(4000)]) {
      const value = shot(); continuity(value)[key] = text;
      expect(checkedCreativeShot(value).continuity?.[key as 'time' | 'lighting']).toBe(text);
    }
    for (const invalid of ['x'.repeat(4001), '🌄'.repeat(4001), 1, false, [], {}, undefined]) {
      const value = shot(); continuity(value)[key] = invalid; expect(() => checkedCreativeShot(value)).toThrow();
    }
  });
  it('still rejects unknown keys, self/missing neighbors and invalid original IDs', () => {
    const value = shot(); continuity(value).time = 'dawn'; continuity(value).lighting = 'blue';
    continuity(value).execute = 'extra'; expect(() => checkedCreativeShot(value)).toThrow(); delete continuity(value).execute;
    continuity(value).previous_shot_id = value.id; expect(() => checkedCreativeShot(value)).toThrow(); delete continuity(value).previous_shot_id;
    value.id = ''; expect(() => checkedCreativeShot(value)).toThrow();
    const saved = copy(fixture); Object.assign(saved.shots[0].shot.continuity, { time: 'dawn', lighting: 'blue', next_shot_id: 'missing' });
    expect(() => checkedStoryboardReceipt(saved)).toThrow();
  });
  it('reads saved storyboard receipts and planning projections with both optional dimensions intact', () => {
    const saved = copy(fixture); Object.assign(saved.shots[0].shot.continuity, { time: '清晨', lighting: '窗边柔光' });
    const receipt = checkedStoryboardReceipt(saved);
    expect(receipt.shots[0].shot.continuity).toMatchObject({ time: '清晨', lighting: '窗边柔光' });
    const source = copy(planning.run.node_states.director.output.direction);
    const projected = checkedPlanningProjection({ ...source, content: { ...source.content, mode: 'STORYBOARD', shots: receipt.shots.map(row => row.shot), scenes: [{ ...source.content.scenes[0], id: receipt.shots[0].shot.scene_id }], director_notes: [] } }, 'STORYBOARD');
    expect(projected.content.shots[0].continuity).toEqual(receipt.shots[0].shot.continuity);
  });
  it('admits the exact saved original board to the image journey without dropping these fields', async () => {
    const saved = copy(fixture); Object.assign(saved.shots[0].shot.continuity, { time: '清晨', lighting: '窗边柔光' });
    const document: CreativeDocument = { ...newDocument('STORYBOARD'), id: saved.document_snapshot.id, version: saved.document_snapshot.version,
      status: 'DRAFT', actor_id: 'owner', created_at: '', updated_at: '', source_evidence: {}, shots: saved.shots.map(row => row.shot) };
    const access: StoryboardImageAccess = { document, projectId: 'project', branchId: null, available: true, isCurrent: () => true, read: async work => work(), onDenied: vi.fn(),
      client: { get: vi.fn().mockResolvedValue(document), storyboardGet: vi.fn().mockResolvedValue(saved) }, studio: { asset: vi.fn(), downloadBounded: vi.fn() } };
    const receipt = await readStoryboardImageReceipt(access, () => true, new AbortController().signal);
    expect(receipt.shots[0].shot.continuity).toMatchObject({ time: '清晨', lighting: '窗边柔光' });
    expect(access.studio.asset).not.toHaveBeenCalled(); expect(access.studio.downloadBounded).not.toHaveBeenCalled();
  });
});
