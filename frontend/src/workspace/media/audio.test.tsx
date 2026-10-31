// @vitest-environment jsdom
// [HERMIA-FE-20261025 AUDIO-T] Evidence kind: mock (in-memory doubles of studioProductionClient). Not real provider/API.
import {describe, expect, it, vi} from 'vitest';
import {act, fireEvent, render, screen, cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';
import {job as baseJob, D} from '../results/u4.fixtures';
import {fromProductionJob, fromTaskCenter} from '../tasks/taskSources';
import {MEDIA_SLICES, UNIFIED_PANELS, layoutSpecs, validateRegistry} from '../registry/workspaceRegistry';
import {audioCandidateInfo, filterByMedia, mediaOfRef} from './mediaSlice';
import {AudioCandidatePreview} from './AudioCandidatePreview';
import type {ProductionJob} from '../../creative/studioProductionClient';

afterEach(cleanup);
const aud = (p: Partial<ProductionJob> = {}) => baseJob({owner: 'audio', id: 'aj-1', operation_id: 'm8.audio.speech', status: 'AWAITING_REVIEW',
  output_candidate: {id: 'asset-a1', version: 1, digest: D('e'), kind: 'audio'}, approved_asset_version: null,
  media_measurement: {duration_ms: 2500, container: 'wav', sample_rate: 48000, channels: 2}, ...p} as Partial<ProductionJob>);
const lease = () => { const l = {epoch: 1, cur: true, isCurrent() { return l.cur; }}; return l; };
const url = () => ({n: 0, revoked: [] as string[], create(this: {n: number}) { return `blob:u${++this.n}`; }, revoke(this: {revoked: string[]}, u: string) { this.revoked.push(u); }});
const RAW = /aj-1|asset-a1|m8\.audio|eeee/;

describe('audio slice reuses the shared registry (no second panel/state system)', () => {
  it('audio slice is active and adds NO separate audio panel; registry still valid', () => {
    expect(MEDIA_SLICES.audio.state).toBe('active');
    expect(UNIFIED_PANELS.filter(p => p.media === 'audio')).toEqual([]);
    expect(layoutSpecs().map(s => s.id)).toEqual(UNIFIED_PANELS.map(p => p.id));
    expect(validateRegistry()).toEqual([]);
  });
  it('media filter over the SAME TaskRef list; task-center rows are not media-typed', () => {
    const tc = fromTaskCenter({authority: 'a', id: 't', status: 'RUNNING', version: 1, label: 'x', stale: false} as never);
    const rows = [fromProductionJob(aud()), fromProductionJob(baseJob()), tc];
    expect(filterByMedia(rows, 'audio').map(r => r.id)).toEqual(['audio:aj-1']);
    expect(filterByMedia(rows, 'image').map(r => r.id)).toEqual(['image:job-1']);
    expect(filterByMedia(rows, 'all')).toHaveLength(3);
    expect(mediaOfRef(tc)).toBeNull();
    expect(fromProductionJob(aud()).title).toBe('音频任务');
  });
});

describe('audioCandidateInfo', () => {
  it('playable candidate with human text only', () => {
    const i = audioCandidateInfo(aud());
    expect(i.playable).toBe(true);
    expect(i.text).toBe('配音候选，可手动试听。试听只读取已返回的文件，不会重新生成。');
    expect(i.durationText).toBe('2.5 秒'); expect(i.formatText).toBe('WAV · 48 kHz · 立体声');
    expect(i.hasWorkLocation).toBe(false);
    expect(JSON.stringify(i)).not.toMatch(RAW);
  });
  it('UNKNOWN / reconciliation / no candidate / non-audio kind / non-audio owner are not playable', () => {
    expect(audioCandidateInfo(aud({status: 'UNKNOWN'})).playable).toBe(false);
    expect(audioCandidateInfo(aud({needs_reconciliation: true} as never)).text).toMatch(/结果未知/);
    expect(audioCandidateInfo(aud({output_candidate: null})).playable).toBe(false);
    expect(audioCandidateInfo(aud({output_candidate: {id: 'x', version: 1, digest: D('f'), kind: 'image'}})).playable).toBe(false);
    expect(audioCandidateInfo(baseJob()).playable).toBe(false);
  });
});

describe('AudioCandidatePreview (explicit read-only GET)', () => {
  it('no read on mount; one GET on click; double click → one request; no autoplay', async () => {
    let resolve!: (b: Blob) => void;
    const reader = {candidate: vi.fn(() => new Promise<Blob>(r => { resolve = r; }))};
    render(<AudioCandidatePreview job={aud()} reader={reader} lease={lease()} url={url()} />);
    expect(reader.candidate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('aud-load')); fireEvent.click(screen.getByTestId('aud-load'));
    expect(reader.candidate).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(new Blob(['x'], {type: 'audio/wav'})); });
    const p = screen.getByTestId('aud-player') as HTMLAudioElement;
    expect(p.getAttribute('src')).toBe('blob:u1'); expect(p.autoplay).toBe(false);
    expect(screen.getByTestId('aud-preview').textContent).not.toMatch(RAW);
  });
  it('late response after scope change is dropped', async () => {
    let resolve!: (b: Blob) => void; const l = lease(); const u = url();
    const reader = {candidate: vi.fn(() => new Promise<Blob>(r => { resolve = r; }))};
    render(<AudioCandidatePreview job={aud()} reader={reader} lease={l} url={u} />);
    fireEvent.click(screen.getByTestId('aud-load'));
    l.cur = false; l.epoch = 2;
    await act(async () => { resolve(new Blob(['x'], {type: 'audio/wav'})); });
    expect(screen.queryByTestId('aud-player')).toBeNull(); expect(u.n).toBe(0);
  });
  it('failure → message, no automatic retry; non-audio blob rejected', async () => {
    const reader = {candidate: vi.fn().mockRejectedValueOnce(new Error('net')).mockResolvedValueOnce(new Blob(['<html>'], {type: 'text/html'}))};
    render(<AudioCandidatePreview job={aud()} reader={reader} lease={lease()} url={url()} />);
    await act(async () => { fireEvent.click(screen.getByTestId('aud-load')); });
    expect(screen.getByTestId('aud-msg').textContent).toBe('读取候选音频失败。检查网络后可以再点一次「试听候选」；不会自动重试。');
    expect(reader.candidate).toHaveBeenCalledTimes(1);
    await act(async () => { fireEvent.click(screen.getByTestId('aud-load')); });
    expect(screen.getByTestId('aud-msg').textContent).toBe('返回的文件不是可播放的音频，已忽略。可以到原任务界面核对。');
    expect(screen.queryByTestId('aud-player')).toBeNull();
  });
  it('UNKNOWN job: button disabled, never reads; no-location note shown for non-trim jobs', () => {
    const reader = {candidate: vi.fn()};
    render(<AudioCandidatePreview job={aud({status: 'UNKNOWN'})} reader={reader} lease={lease()} url={url()} />);
    expect((screen.getByTestId('aud-load') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId('aud-load')); expect(reader.candidate).not.toHaveBeenCalled();
    expect(screen.getByTestId('aud-no-location')).toBeTruthy();
  });
});
