/**
 * [HERMIA-FE-20261025 AUDIO-M10] Explicit, read-only audio candidate preview for a selected audio production job.
 * - Nothing is read on mount; the user presses 「试听候选」 → ONE GET candidate(job) via the existing client.
 * - Double click while loading = one request; failure is not retried automatically.
 * - Bound to the ScopeLease: a response after project/identity switch is dropped (and the object URL revoked).
 * - No autoplay; <audio controls> only. No review/adopt here — those stay in the shared ResultsPanel.
 */
import {useEffect, useRef, useState} from 'react';
import type {ProductionJob} from '../../creative/studioProductionClient';
import type {ScopeLease} from '../contracts';
import {audioCandidateInfo} from './mediaSlice';

export interface AudioCandidateReader { candidate(job: ProductionJob): Promise<Blob>; }
type Url = {create(b: Blob): string; revoke(u: string): void};
const defaultUrl: Url = {create: b => URL.createObjectURL(b), revoke: u => URL.revokeObjectURL(u)};

export function AudioCandidatePreview({job, reader, lease, url = defaultUrl}: {job: ProductionJob; reader: AudioCandidateReader; lease: Pick<ScopeLease, 'epoch' | 'isCurrent'>; url?: Url}) {
  const info = audioCandidateInfo(job);
  const [src, setSrc] = useState<string | null>(null), [msg, setMsg] = useState(''), [busy, setBusy] = useState(false);
  const inflight = useRef(false), current = useRef<string | null>(null);
  useEffect(() => () => { if (current.current) url.revoke(current.current); current.current = null; }, [job, url]);
  useEffect(() => { setSrc(null); setMsg(''); }, [job]);
  async function load() {
    if (inflight.current || !info.playable) return;
    inflight.current = true; setBusy(true); setMsg('');
    const epoch = lease.epoch;
    try {
      const b = await reader.candidate(job);
      if (!lease.isCurrent() || lease.epoch !== epoch) return;
      if (!b.type.startsWith('audio/')) { setMsg('返回的文件不是可播放的音频，已忽略。可以到原任务界面核对。'); return; }
      if (current.current) url.revoke(current.current);
      current.current = url.create(b); setSrc(current.current);
    } catch {
      if (lease.isCurrent() && lease.epoch === epoch) setMsg('读取候选音频失败。检查网络后可以再点一次「试听候选」；不会自动重试。');
    } finally { inflight.current = false; if (lease.isCurrent()) setBusy(false); }
  }
  return <div data-testid="aud-preview" data-job-owner={job.owner} data-playable={info.playable ? '1' : '0'} aria-label="音频候选">
    <p data-testid="aud-info">{info.text}{info.durationText ? ` 时长 ${info.durationText}。` : ''}{info.formatText ? ` 格式 ${info.formatText}。` : ''}</p>
    {!info.hasWorkLocation && <p data-testid="aud-no-location">这个音频任务没有记录作品位置（目前只有音频裁剪任务会记录），所以不能从这里采用到作品。</p>}
    <button type="button" data-testid="aud-load" onClick={() => void load()} disabled={!info.playable || busy}>{busy ? '正在读取…' : '试听候选'}</button>
    {src && <audio data-testid="aud-player" controls preload="metadata" src={src} />}
    {msg && <p role="status" data-testid="aud-msg">{msg}</p>}
  </div>;
}
