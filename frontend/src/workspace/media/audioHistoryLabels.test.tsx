// @vitest-environment jsdom
// [HERMIA-FE-CONTRACTS G-AUD-5] restore = undelete; Timeline history is the only version history; single-asset history unsupported.
import {cleanup, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {AUDIO_HISTORY_TEXT} from './audioHistoryText';
import {AudioCandidatePreview} from './AudioCandidatePreview';
import {audioJob} from '../../creative/studioAudioWav.testFixtures';
import {studioProductionClient, type ProductionJob} from '../../creative/studioProductionClient';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('audio history labels', () => {
  it('names asset restore as undelete and single-asset history as unsupported', () => {
    expect(AUDIO_HISTORY_TEXT.assetRestore).toBe('撤销删除');
    expect(AUDIO_HISTORY_TEXT.assetRestoreHint).toMatch(/不是回到旧版本/);
    expect(AUDIO_HISTORY_TEXT.timelineOnly).toMatch(/时间线/);
    expect(AUDIO_HISTORY_TEXT.assetHistory).toMatch(/暂不支持/);
  });
  it('audio candidate preview states the history boundary', () => {
    render(<AudioCandidatePreview job={audioJob() as unknown as ProductionJob} reader={{candidate: vi.fn()}} lease={{epoch: 1, isCurrent: () => true}} />);
    const note = screen.getByTestId('aud-history-note').textContent ?? '';
    expect(note).toContain('暂不支持'); expect(note).toContain('时间线');
  });
});
describe('timeline history client (contract shape only)', () => {
  it('reads history and restores with the four reviewed fields', async () => {
    const calls: [string, RequestInit][] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => { calls.push([url, init]);
      return {ok: true, status: 200, json: async () => (url.endsWith('/history') ? {timeline_id: 't1', current_version: 2, items: []} : {})}; }));
    const c = studioProductionClient('p1', {sessionToken: '', localHostToken: ''});
    const h = await c.timelineHistoryRaw('t1');
    expect(calls[0][0]).toBe('/api/projects/p1/studio/production/timelines/t1/history');
    expect(h).toEqual({timeline_id: 't1', current_version: 2, items: []});
    await expect(c.timelineHistoryRaw('t1')).resolves.toBeTruthy();
    await c.timelineRestoreRaw('t1', {expected_version: 2, reviewed_timeline_digest: 'a'.repeat(64), restore_version: 1, restore_digest: 'b'.repeat(64)}).catch(() => undefined);
    const [url, init] = calls[2];
    expect(url).toBe('/api/projects/p1/studio/production/timelines/t1/restore');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({expected_version: 2, reviewed_timeline_digest: 'a'.repeat(64), restore_version: 1, restore_digest: 'b'.repeat(64)});
  });
  it('rejects malformed history and malformed restore input', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ok: true, status: 200, json: async () => ({timeline_id: 'other', current_version: 2, items: []})})));
    const c = studioProductionClient('p1', {sessionToken: '', localHostToken: ''});
    await expect(c.timelineHistoryRaw('t1')).rejects.toThrow();
    await expect(c.timelineRestoreRaw('t1', {expected_version: 2, reviewed_timeline_digest: 'x', restore_version: 1, restore_digest: 'b'.repeat(64)})).rejects.toThrow();
  });
});
