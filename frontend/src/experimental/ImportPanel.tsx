import { useEffect, useState } from 'react';
import type { Chapter } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, RecordStatus, Refresh, ResourceState, ids, useAction, useResource } from './shared';

export function ImportPanel({ client, chapter, requestedTaskId }: { client: ExperimentalClient; chapter?: Chapter; requestedTaskId?: string }) {
  const [chapterIds, setChapterIds] = useState(chapter?.id || ''), [chunkSize, setChunkSize] = useState(8000), [overlap, setOverlap] = useState(256), [jobId, setJobId] = useState(requestedTaskId || '');
  useEffect(() => { if (requestedTaskId) setJobId(requestedTaskId); }, [requestedTaskId, client]);
  const jobs = useResource(signal => client.get<Rows>('/imports/jobs', signal), [client]);
  const review = useResource(async signal => {
    if (!jobId) return { candidates: [], chunks: [] };
    const [candidates, chunks] = await Promise.all([client.get<Rows>(`/imports/candidates?job_id=${segment(jobId)}`, signal), client.get<Rows>(`/imports/jobs/${segment(jobId)}/chunks`, signal)]);
    return { candidates: candidates.items, chunks: chunks.items };
  }, [client, jobId]);
  const reload = () => { jobs.reload(); review.reload(); };
  const action = useAction(reload), [selected, setSelected] = useState<string[]>([]), [confirmed, setConfirmed] = useState(false);
  const job = jobs.data?.items.find(row => row.id === jobId);
  useEffect(() => { if (!requestedTaskId && !jobId && jobs.data?.items[0]) setJobId(jobs.data.items[0].id); }, [jobId, jobs.data]);
  useEffect(() => { setSelected([]); setConfirmed(false); }, [jobId]);
  const transition = (operation: string, extras = {}) => job && action.run(() => client.post(`/imports/jobs/${segment(job.id)}/${operation}`, { expected_version: job.version, ...extras }), '导入任务已更新');
  const candidates = review.data?.candidates || [];
  const selectedRows = candidates.filter(row => selected.includes(row.id));
  const approved = candidates.filter(row => row.status === 'APPROVED' && !row.stale);
  const reviewCandidate = (row: Row, operation: string) => action.run(() => client.post(`/imports/candidates/${segment(row.id)}/review`, { expected_version: row.version, action: operation }), '候选审核已更新');
  const busy = action.busy || jobs.loading || review.loading;
  return <Panel title="长篇分块导入 V2" actions={<Refresh reload={reload} busy={busy} />}>
    <StatusMessage>LOCAL_HEURISTIC 确定性提取。每项保留来源证据，审核后才可明确提交；这不代表真实模型语义质量。</StatusMessage>
    {requestedTaskId && !jobs.loading && !jobs.error && !jobs.data?.items.some(row => row.id === requestedTaskId) && <StatusMessage tone="warning">请求的原导入任务当前不可读或已移除；未改选其他任务。</StatusMessage>}
    {action.feedback}<ResourceState loading={jobs.loading || review.loading} error={jobs.error || review.error} />
    <Form onSubmit={() => action.run(async () => { const result = await client.post<Row>('/imports/jobs', { chapter_ids: ids(chapterIds), chunk_size: chunkSize, overlap, adapter_id: 'local-semantic-rules-v2' }); setJobId(result.id); }, '分块任务已创建')}>
      <Field label="导入来源章节 ID（逗号分隔）"><input required value={chapterIds} onChange={event => setChapterIds(event.target.value)} /></Field>
      <div className="experimental-grid"><Field label="分块字符数"><input type="number" min={256} max={32000} value={chunkSize} onChange={event => setChunkSize(Number(event.target.value))} /></Field><Field label="重叠字符数"><input type="number" min={0} max={1024} value={overlap} onChange={event => setOverlap(Number(event.target.value))} /></Field></div>
      <Button type="submit" disabled={busy || !ids(chapterIds).length}>创建分块导入</Button>
    </Form>
    {!!jobs.data?.items.length && <Field label="导入任务"><select value={jobId} onChange={event => setJobId(event.target.value)}>{jobs.data.items.map(row => <option key={row.id} value={row.id}>{row.id.slice(0, 8)} · {row.status}</option>)}</select></Field>}
    {job && <section className="experimental-record" aria-label="导入任务状态"><RecordStatus row={job} /><p>分块 {job.completed_chunks} / {job.total_chunks} · 候选 {job.candidate_count}</p><Details value={job.sources} label="章节版本与内容 hash" />
      <div className="experimental-actions">{['QUEUED', 'ANALYZING'].includes(job.status || '') && <><Button disabled={busy} onClick={() => transition('process', { max_chunks: 1 })}>处理下一分块</Button><Button disabled={busy} onClick={() => transition('pause')}>暂停导入</Button></>}{job.status === 'PAUSED' && <Button disabled={busy} onClick={() => transition('resume')}>恢复导入</Button>}{job.status === 'FAILED' && <Button disabled={busy} onClick={() => transition('retry')}>重试失败分块</Button>}{job.status === 'ANALYZING' && <Button disabled={busy} onClick={() => transition('recover')}>检查中断恢复</Button>}{['QUEUED', 'ANALYZING', 'PAUSED', 'FAILED', 'NEEDS_REVIEW', 'STALE'].includes(job.status || '') && <Button disabled={busy} onClick={() => transition('cancel')}>取消导入</Button>}</div>
      <Details label="分块与 checkpoint" value={review.data?.chunks} />
    </section>}
    {!!candidates.length && <><h3>逐项来源审核</h3><div className="experimental-actions"><Button disabled={busy || !selectedRows.length || selectedRows.some(row => row.stale || row.status === 'COMMITTED')} onClick={() => action.run(() => client.post(`/imports/jobs/${segment(jobId)}/review-batch`, { items: selectedRows.map(row => ({ id: row.id, expected_version: row.version, action: 'approve' })) }), '所选候选均已通过来源校验与审核')}>批量批准已选候选</Button></div></>}
    <div className="experimental-list">{candidates.map(row => <article className="experimental-record" key={row.id} aria-label={`导入候选 ${row.label}`}><label className="experimental-check"><input type="checkbox" disabled={row.status === 'COMMITTED'} checked={selected.includes(row.id)} onChange={event => setSelected(current => event.target.checked ? [...current, row.id] : current.filter(id => id !== row.id))} />{row.kind} · {row.label}</label><RecordStatus row={row} /><Details value={row.source_evidence} label="原文证据（章节 / 版本 / offset / hash）" /><Details value={{ value: row.value, conflicts: row.conflicts, resolution_suggestions: row.resolution_suggestions }} label="实体消歧与冲突" />{!['COMMITTING', 'COMMITTED'].includes(row.status || '') && <div className="experimental-actions"><Button disabled={busy || row.stale || !['NEEDS_REVIEW', 'STALE'].includes(job?.status || '')} onClick={() => reviewCandidate(row, 'approve')}>批准导入候选</Button><Button disabled={busy} onClick={() => reviewCandidate(row, 'reject')}>驳回导入候选</Button>{['APPROVED', 'REJECTED'].includes(row.status || '') && <Button disabled={busy} onClick={() => reviewCandidate(row, 'reopen')}>重开导入候选</Button>}</div>}</article>)}</div>
    {job && ['NEEDS_REVIEW', 'COMMITTING'].includes(job.status || '') && <section className="experimental-record"><p>提交将把已批准候选写入故事资料。未支持的类型会被服务端阻止；失败时保留 checkpoint，禁止重复写入。</p><label className="experimental-check"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />我已核对 {approved.length} 项已批准候选与来源证据</label><Button disabled={busy || !confirmed || !approved.length} onClick={() => transition('commit', { candidate_ids: approved.map(row => row.id) })}>提交已批准导入</Button></section>}
  </Panel>;
}
