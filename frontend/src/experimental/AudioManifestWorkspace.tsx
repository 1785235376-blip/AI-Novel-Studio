import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { audioManifestClient, type AudioManifest, type AudioPreview, type AudioResult, type AudioRecord } from './audioManifestClient';
import { Details, Field } from './shared';

type Props = { client: ExperimentalClient; onInteraction?: () => void };
function AudioManifestRead({ client, onInteraction }: Props) {
  const api = useMemo(() => audioManifestClient(client), [client]);
  const [results, setResults] = useState<AudioResult[]>(), [records, setRecords] = useState<AudioManifest[]>();
  const [jobId, setJobId] = useState(''), [preview, setPreview] = useState<AudioPreview>(), [opened, setOpened] = useState<AudioManifest>();
  const [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const live = useRef({ active: true, generation: 0, running: false, consent: false, requestId: '' });
  const abort = useRef<AbortController>(); const generation = live.current.generation;
  useLayoutEffect(() => { live.current.active = true; return () => { live.current.active = false; live.current.generation++; abort.current?.abort(); }; }, []);
  const current = (ticket: number) => live.current.active && live.current.generation === ticket;
  const clearPrivate = () => { setResults(undefined); setRecords(undefined); setPreview(undefined); setOpened(undefined); setJobId(''); live.current.consent = false; setConfirmed(false); };
  const begin = () => {
    if (!live.current.active || live.current.running || live.current.generation !== generation) return undefined;
    onInteraction?.(); live.current.running = true; const ticket = ++live.current.generation;
    abort.current?.abort(); abort.current = new AbortController(); live.current.consent = false; setConfirmed(false); setBusy(true); setNotice(''); return ticket;
  };
  const finish = (ticket: number) => { if (current(ticket)) { live.current.running = false; setBusy(false); } };
  const denied = (ticket: number) => { if (current(ticket)) { clearPrivate(); setNotice('音频清单不可用或当前来源、权限已改变。共享入口尚未接线时也会不可用；没有记录或执行新任务。'); } };
  const read = async () => {
    const ticket = begin(); if (ticket === undefined) return; clearPrivate();
    try {
      const [available, saved] = await Promise.all([api.results(abort.current!.signal), api.list(abort.current!.signal)]);
      if (!current(ticket)) return; setResults(available); setRecords(saved);
      if (live.current.requestId) {
        const found = saved.find(row => row.request_id === live.current.requestId);
        if (found) { setOpened(found); live.current.requestId = ''; setUncertain(false); setNotice('已通过授权读取核对原记录，没有再次发送。'); }
        else setNotice('读取未找到原记录；这不能证明记录失败，仍保留未知状态，不会换键重试。');
      }
    } catch { denied(ticket); } finally { finish(ticket); }
  };
  const inspect = async () => {
    const selected = results?.find(row => row.id === jobId), ticket = begin(); if (ticket === undefined) return;
    setPreview(undefined); setOpened(undefined);
    try {
      if (!selected) throw new Error('请选择原音频结果');
      const value = await api.preview(selected.id, abort.current!.signal);
      if (value.capture.job.id !== selected.id || value.capture.job.version !== selected.version) throw new Error('结果已变化');
      if (current(ticket)) setPreview(value);
    } catch { denied(ticket); } finally { finish(ticket); }
  };
  const record = async () => {
    if (!preview || !live.current.consent || live.current.requestId) return;
    const selected = preview, ticket = begin(); if (ticket === undefined) return;
    const request: AudioRecord = { job_id: selected.capture.job.id, expected_job_version: selected.capture.job.version,
      reviewed_capture_digest: selected.capture_digest, request_id: crypto.randomUUID(), confirmed: true };
    live.current.requestId = request.request_id;
    try {
      const value = await api.record(request);
      if (value.request_id !== request.request_id || value.capture_digest !== selected.capture_digest || JSON.stringify(value.capture) !== JSON.stringify(selected.capture)) throw new Error('记录回执不匹配');
      if (current(ticket)) { setOpened(value); setRecords(items => [value, ...(items || []).filter(row => row.id !== value.id)]); setPreview(undefined); live.current.requestId = ''; setUncertain(false); setNotice('已人工记录原审核音频清单；没有创建、执行、重放或审核任务。'); }
    } catch {
      if (current(ticket)) { clearPrivate(); setUncertain(true); setNotice('记录响应未核对，结果未知。只保留原请求标识；请手动读取原记录，不会自动重试或换键记录。'); }
    } finally { finish(ticket); }
  };
  const reopen = async (saved: AudioManifest) => {
    const ticket = begin(); if (ticket === undefined) return; setOpened(undefined); setPreview(undefined);
    try {
      const value = await api.get(saved.id, abort.current!.signal);
      if (value.id !== saved.id || value.manifest_digest !== saved.manifest_digest) throw new Error('清单已变化');
      if (current(ticket)) setOpened(value);
    } catch { denied(ticket); } finally { finish(ticket); }
  };
  const download = async () => {
    if (!opened) return; const saved = opened, ticket = begin(); if (ticket === undefined) return;
    try {
      const value = await api.export(saved.id, abort.current!.signal);
      if (value.id !== saved.id || value.manifest_digest !== saved.manifest_digest) throw new Error('导出回执已变化');
      if (current(ticket)) {
        const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
        try { const link = document.createElement('a'); link.href = url; link.download = 'studio-audio-manifest.json'; link.click(); }
        finally { URL.revokeObjectURL(url); }
        setNotice('已导出当前授权核对的音频清单 JSON；本切片不支持重放。');
      }
    } catch { denied(ticket); } finally { finish(ticket); }
  };
  return <section className="experimental-section" aria-label="现代 Studio Audio 结果清单">
    <h3>现代 Studio Audio 结果清单</h3>
    <StatusMessage>仅记录原 Audio owner 已人工审核并成为正式资产的结果。本入口不重放、不创建任务、不自动审核；模型哈希、运行环境与硬件证据：未知。</StatusMessage>
    <Button disabled={busy} onClick={() => { void read(); }}>读取已审核音频与清单</Button>
    {busy && <StatusMessage>正在重新核对原音频读取授权…</StatusMessage>}
    {notice && <StatusMessage>{notice}</StatusMessage>}
    {uncertain && <StatusMessage tone="warning">原记录仍待核对，暂不接受新的记录动作。可手动读取原清单。</StatusMessage>}
    {results && <><Field label="已审核的现代音频结果"><select value={jobId} disabled={busy || uncertain} onChange={event => {
      onInteraction?.(); live.current.generation++; live.current.consent = false; setConfirmed(false); setPreview(undefined); setOpened(undefined); setJobId(event.target.value);
    }}><option value="">选择原 Audio 结果</option>{results.map(row => <option key={row.id} value={row.id}>{row.operation_id} · {row.id} · v{row.version}</option>)}</select></Field>
    <Button disabled={busy || !jobId || uncertain} onClick={() => { void inspect(); }}>核对所选音频结果与正式资产</Button>
    {!results.length && <EmptyState title="暂无可核对的已审核音频结果" detail="请先通过原 Audio 任务流程人工审核；这里不会创建或审核结果。" />}</>}
    {preview && <section aria-label="音频清单记录前核对">
      <p>原 Audio 任务 {preview.capture.job.id} · v{preview.capture.job.version} · {preview.capture.job.operation_id}</p>
      <p>请求摘要：{preview.capture.job.request_digest}</p><p>已审核输出摘要：{preview.capture.result.output_digest}</p>
      <p>正式音频资产 {preview.capture.asset.id} · v{preview.capture.asset.version}；已核对来源 {preview.capture.sources.length} 项。</p>
      <Details value={preview} label="完整绑定与原审核回执摘要" />
      <label><input type="checkbox" checked={confirmed} disabled={busy || uncertain} onChange={event => {
        onInteraction?.(); live.current.generation++; live.current.consent = event.target.checked; setConfirmed(event.target.checked);
      }} />已核对原任务版本、请求与输出摘要、正式资产版本，明确记录此次清单</label>
      <Button disabled={busy || !confirmed || uncertain} onClick={() => { void record(); }}>明确记录所选音频清单</Button></section>}
    {records && <div className="experimental-actions" aria-label="现代音频清单列表">{records.map(row => <Button key={row.id} disabled={busy} onClick={() => { void reopen(row); }}>重开音频清单 {row.capture.job.id} · {row.id}</Button>)}</div>}
    {opened && <section aria-label="已核对的现代音频清单">
      <p>已记录音频清单 {opened.id} · v{opened.version}</p>
      <p>原任务 {opened.capture.job.id} · v{opened.capture.job.version}；正式资产 {opened.capture.asset.id} · v{opened.capture.asset.version}</p>
      <p>已审核输出摘要：{opened.capture.result.output_digest}</p>
      <Details value={opened} label="已保存音频清单详情" /><Button disabled={busy} onClick={() => { void download(); }}>导出已核对音频清单 JSON</Button></section>}
  </section>;
}

export function AudioManifestWorkspace(props: Props) {
  const identity = useRef({ client: props.client, generation: 0 });
  if (identity.current.client !== props.client) identity.current = { client: props.client, generation: identity.current.generation + 1 };
  return <AudioManifestRead key={identity.current.generation} {...props} />;
}
