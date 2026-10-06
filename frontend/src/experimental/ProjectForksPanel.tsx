import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { projectForksClient, type ForkChoice, type ForkComparison, type ForkNode, type ForkRecord, type ForkRecovery } from './projectForksClient';
import { SharedUniversePanel } from './SharedUniversePanel';
import { StructuredForksPanel } from './StructuredForksPanel';
let nextScope = 0;
type ForkApi = ReturnType<typeof projectForksClient>;
const stages: Record<string, string> = { PREFLIGHT: '待确认分叉', FORKED: '分叉已建立', CLAIMED: '已记录写入意图', APPLYING: '正在写入或结果待核对', RECOVERY_REQUIRED: '需要恢复核对', COMPLETED: '合并完成', RESTORED: '检查点已恢复', RESTORING_CHECKPOINT: '检查点恢复处理中' };
export function ProjectForksPanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++nextScope, [client]);
  return <ForksContent key={identity} client={client} />;
}
function ForksContent({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => projectForksClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]); const records = useResource(signal => api.records(signal), [api]);
  const action = useReviewAction(); const [selected, setSelected] = useState<string[]>([]); const [title, setTitle] = useState('');
  const [showStructured, setShowStructured] = useState(false);
  const [showUniverse, setShowUniverse] = useState(false);
  const [operationError, setOperationError] = useState<unknown>(); const [receipt, setReceipt] = useState('');
  const report = (error: unknown, message = '') => { setOperationError(error); setReceipt(message); };
  const [licenses, setLicenses] = useState<Record<string, string>>({}); const [permissions, setPermissions] = useState<Record<string, boolean>>({});
  const available = !catalog.loading && !catalog.error && !!catalog.data?.available;
  const readyRecords = !records.loading && !records.error && records.data;
  const assets = available ? catalog.data!.assets.filter(a => catalog.data!.chapters.some(c => selected.includes(c.id) && c.asset_ids.includes(a.id))) : [];
  const refresh = () => { catalog.reload(); records.reload(); setPermissions({}); };
  return <section className="experimental-section" aria-label="项目分叉与合并">
    <div className="experimental-actions"><h3>项目分叉与合并</h3><Badge>本地新项目 · 逐项三方审核</Badge><Button disabled={action.busy} onClick={refresh}>刷新分叉与合并记录</Button></div>
    <p>从选中的已保存章节建立新项目，保留分叉基线。修改副本后，在这里比较基线、当前原稿与当前副本，明确选择冲突再合并回原稿。新旧项目都会保留。</p>
    <StatusMessage>这不是 Git 分支或协作分支。协作分支正文尚无独立存储与写入服务，不能将基础正文当作分支内容。此正文入口不复制结构记录；人物、地点与关系可在下方单独选择和审核。Canon、Workflow、历史与权限不会复制。新增或改变的副本媒体引用需要另外的映射流程，当前会阻止合并。</StatusMessage>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!catalog.loading && !catalog.error && !catalog.data?.available && <StatusMessage tone="warning">当前协作范围不能建立或合并本地项目分叉。不会读取其他分支的基础正文。</StatusMessage>}
    {!!operationError && <ErrorMessage error={operationError} />}{receipt && <StatusMessage tone="success">{receipt}</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    <Panel title="选择分叉范围与媒体许可">
      <Field label="新分叉项目名称"><input value={title} maxLength={160} disabled={action.busy} onChange={e => setTitle(e.target.value)} /></Field>
      {available && !catalog.data!.chapters.length && <EmptyState title="没有已授权章节" detail="先在原编辑器保存正文。分叉只读取已保存版本。" />}
      {available && catalog.data!.chapters.map(c => <label className="experimental-check" key={c.id}><input type="checkbox" checked={selected.includes(c.id)} disabled={action.busy || c.supported === false || (!selected.includes(c.id) && selected.length >= 40)} onChange={e => { setSelected(ids => e.target.checked ? [...ids, c.id] : ids.filter(id => id !== c.id)); setPermissions({}); }} />{c.title} · v{c.version}{c.supported === false ? '（含暂不支持的富文本结构）' : ''}</label>)}
      {assets.map(asset => <article key={asset.id} className="experimental-record"><p>{asset.filename} · {asset.available === false ? '缺失、不可访问或格式不支持' : `v${asset.version}`}</p><Details label="查看媒体来源 ID 与摘要" value={asset} /><Field label={`媒体许可说明：${asset.filename}`}><input value={licenses[asset.id] || ''} maxLength={240} disabled={action.busy} onChange={e => { setLicenses(v => ({ ...v, [asset.id]: e.target.value })); setPermissions(v => ({ ...v, [asset.id]: false })); }} /></Field><label className="experimental-check"><input type="checkbox" checked={!!permissions[asset.id]} disabled={action.busy || asset.available === false || !licenses[asset.id]?.trim()} onChange={e => setPermissions(v => ({ ...v, [asset.id]: e.target.checked }))} />我有权将 {asset.filename} 复制到此本地分叉</label></article>)}
      <p>媒体许可是作者声明，不是法律核验。只复制原资产库中可读取、摘要一致且明确允许的媒体。</p>
      <Button disabled={action.busy || !available || !title.trim() || !selected.length || selected.some(id => !catalog.data!.chapters.some(c => c.id === id)) || assets.some(a => a.available === false || !licenses[a.id]?.trim() || !permissions[a.id])} onClick={() => void action.run(async current => { await api.preflight(selected, title, assets.map(a => ({ asset_id: a.id, version: a.version, sha256: a.sha256, license: licenses[a.id], allow_local_copy: true }))); if (current()) records.reload(); }, '所选版本与媒体已冻结为待审基线，尚未创建新项目。')}>仅预检所选分叉</Button>
    </Panel>
    <Panel title="分叉记录与三方比较"><ResourceState loading={records.loading} error={records.error} empty={!!readyRecords && !readyRecords.items.length} />
      {readyRecords && readyRecords.items.map(row => <ForkReview key={`${row.id}:${row.version}`} api={api} row={row} available={available} refresh={refresh} report={report} />)}
    </Panel>
    <Button aria-expanded={showStructured} onClick={() => setShowStructured(value => !value)}>{showStructured ? '收起人物与关系分叉' : '打开人物与关系分叉'}</Button>
    {showStructured && <StructuredForksPanel client={client} manuscriptForks={readyRecords ? readyRecords.items : []} />}
    <Button aria-expanded={showUniverse} onClick={() => setShowUniverse(value => !value)}>{showUniverse ? '收起系列世界观快照' : '打开系列世界观快照'}</Button>
    {showUniverse && <SharedUniversePanel client={client} />}
    <Panel title="合并检查点与中断恢复">
      <p>每次合并都先保存完整检查点，再逐项记录写入意图。部分完成或结果未知时不自动重试。恢复需要重新核对当前内容，并以新版本保存检查点。</p>
      {readyRecords && !readyRecords.merges.length && <p>尚无合并检查点。</p>}
      {readyRecords && readyRecords.merges.map(row => <MergeRecovery key={`${row.id}:${row.version}`} api={api} row={row} active={readyRecords.items.some(f => f.active_merge === row.id)} available={available} refresh={refresh} report={report} />)}
    </Panel>
  </section>;
}
function RichNodes({ nodes }: { nodes: ForkNode[] }) {
  const inline = (node: ForkNode, index: number): ReactNode => {
    if (node.type === 'text') {
      let text: ReactNode = node.text || '';
      for (const mark of node.marks || []) { if (mark.type === 'bold') text = <strong>{text}</strong>; else if (mark.type === 'italic') text = <em>{text}</em>; else if (mark.type === 'strike') text = <s>{text}</s>; else if (mark.type === 'code') text = <code>{text}</code>; else if (mark.type === 'underline') text = <u>{text}</u>; else if (mark.type === 'subscript') text = <sub>{text}</sub>; else if (mark.type === 'superscript') text = <sup>{text}</sup>; }
      return <span key={index}>{text}</span>;
    }
    if (node.type === 'hardBreak') return <br key={index} />;
    if (['image', 'audio', 'video'].includes(node.type)) return <p key={index}>媒体引用：{String(node.attrs?.asset_id || '')}</p>;
    return <div key={index}>{!!node.attrs?.aiRevisionLock && <Badge>保留 AI 段落锁</Badge>}{node.content?.map(inline)}</div>;
  };
  return <div className="experimental-preview">{nodes.length ? nodes.map(inline) : <p>（无内容 / 已归档）</p>}</div>;
}
function ForkReview({ api, row, available, refresh, report }: { api: ForkApi; row: ForkRecord; available: boolean; refresh: () => void; report: (error: unknown, message?: string) => void }) {
  const action = useReviewAction(); const [confirmed, setConfirmed] = useState(false); const [preview, setPreview] = useState<ForkComparison>();
  const [choices, setChoices] = useState<Record<string, ForkChoice>>({}); const [dirty, setDirty] = useState(false); const [reviewed, setReviewed] = useState(false);
  useEffect(() => { if (!available) { setPreview(undefined); setReviewed(false); setConfirmed(false); } }, [available]);
  return <article className="experimental-record" aria-label={`分叉 ${row.title || row.id}`}>
    <div className="experimental-actions"><strong>{row.title || row.id}</strong><Badge>{stages[row.status] || row.status} · v{row.version}</Badge></div>
    <p>新项目 ID：{row.target_id} · 所选章节 {row.chapter_count || 0}</p>
    {row.status === 'PREFLIGHT' && <><label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={action.busy || !available} onChange={e => setConfirmed(e.target.checked)} />已核对所选章节与媒体许可，创建此新项目分叉</label><Button disabled={action.busy || !available || !confirmed} onClick={() => void action.run(async current => { report(undefined); try { await api.create(row); if (current()) report(undefined, '分叉已建立。返回项目列表打开新项目，修改后回原项目比较。'); } catch (error) { if (current()) report(error); } finally { if (current()) { setConfirmed(false); refresh(); } } })}>确认创建新项目分叉</Button></>}
    {row.target_available === false && <StatusMessage tone="warning">目标项目不可访问。原项目的操作记录保留；请先恢复目标项目或确认当前权限。</StatusMessage>}
    {row.status === 'FORKED' && row.target_available !== false && <>
      <Button disabled={action.busy || !available} onClick={() => void action.run(async current => { report(undefined); setReviewed(false); const value = await api.compare(row, choices); if (current()) { setPreview(value); setDirty(false); } }, '三方比较已更新，尚未改写原稿。')}>{preview ? '更新合并预览' : '比较基线、原稿与副本'}</Button>
      {!!Object.keys(choices).length && <Button disabled={action.busy} onClick={() => { setChoices({}); setPreview(undefined); setReviewed(false); setDirty(false); }}>清除旧冲突选择</Button>}
      {preview && <section aria-label="三方合并预览"><p>待解决冲突 {preview.unresolved} 项 · 预计改写 {preview.write_count} 个原稿章节。原稿 v / 副本 v 如下；应用时会再次核对两端版本。</p>
        {preview.chapters.map(chapter => <section key={chapter.chapter_id} aria-label={`三方章节 ${chapter.title}`}><h4>{chapter.title} · 原稿 v{chapter.original_version ?? '已删除'} / 副本 v{chapter.fork_version ?? '已删除'}</h4>
          {!chapter.segments.length && <p>此章节没有差异。</p>}
          {chapter.segments.map((segment, index) => <article key={segment.id} className="experimental-record"><Badge tone={segment.kind === 'CONFLICT' ? 'warning' : 'neutral'}>{segment.kind === 'CONFLICT' ? '冲突：需逐项选择' : segment.kind === 'FORK_ONLY' ? '仅副本修改' : segment.kind === 'ORIGINAL_ONLY' ? '仅原稿修改' : '双方修改一致'}</Badge>{segment.reason === 'CHAPTER_DELETION_OR_DELETE_MODIFY' && <StatusMessage tone="warning">删除 / 修改冲突。采用已删除副本会将原稿章节归档，不永久删除。</StatusMessage>}
            <div className="experimental-grid"><section><h5>分叉基线</h5><RichNodes nodes={segment.base} /></section><section><h5>当前原稿</h5><RichNodes nodes={segment.ORIGINAL} /></section><section><h5>当前副本</h5><RichNodes nodes={segment.FORK} /></section></div>
            {segment.kind === 'CONFLICT' && <Field label={`${chapter.title} 冲突 ${index + 1} 选择`}><select value={choices[segment.id] || ''} disabled={action.busy} onChange={e => { const choice = e.target.value as ForkChoice; setChoices(old => { const next = { ...old }; if (choice) next[segment.id] = choice; else delete next[segment.id]; return next; }); setDirty(true); setReviewed(false); }}><option value="">逐项选择</option><option value="ORIGINAL">保留当前原稿</option><option value="FORK">采用当前副本</option></select></Field>}
            <Details label="查看完整富文本结构与引用" value={segment} />
          </article>)}
        </section>)}
        {preview.blocked.map((b, i) => <StatusMessage key={i} tone="warning">{b.chapter_id}：{b.code}。先在原编辑器明确处理段落锁，再重新比较。</StatusMessage>)}
        {dirty && <StatusMessage tone="warning">选择已改变，请更新合并预览后重新确认。</StatusMessage>}
        <label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy || dirty || !preview.can_apply || !available} onChange={e => setReviewed(e.target.checked)} />已逐项核对三方差异，建立检查点并合并回原稿</label>
        <Button disabled={action.busy || !available || dirty || !reviewed || !preview.can_apply || !preview.write_count} onClick={() => void action.run(async current => { report(undefined); try { await api.apply(row, preview, choices); if (current()) report(undefined, '已通过原版本服务合并；检查点、原稿历史与副本保留。'); } catch (error) { if (current()) report(error); } finally { if (current()) { setReviewed(false); setPreview(undefined); refresh(); } } })}>确认检查点并合并</Button>
      </section>}
    </>}
    {['CLAIMED', 'APPLYING', 'RECOVERY_REQUIRED'].includes(row.status) && <StatusMessage tone="warning">新项目创建中断或结果未知。请在原项目列表核对新项目和下方映射；不会重试创建或覆盖已有章节。未完成的副本保留，核对后可重新预检一个新分叉。</StatusMessage>}
    {row.id_map && <Details label="查看稳定章节与资产 ID 映射" value={row.id_map} />}{!!row.assets?.length && <Details label="查看已确认媒体许可与摘要" value={row.assets} />}
    {!!row.journal?.length && <Details label="查看分叉写入记录" value={row.journal} />}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
  </article>;
}
function MergeRecovery({ api, row, active, available, refresh, report }: { api: ForkApi; row: ForkRecord; active: boolean; available: boolean; refresh: () => void; report: (error: unknown, message?: string) => void }) {
  const action = useReviewAction(); const [preview, setPreview] = useState<ForkRecovery>(); const [confirmed, setConfirmed] = useState(false);
  useEffect(() => { if (!available) { setPreview(undefined); setConfirmed(false); } }, [available]);
  return <article className="experimental-record" aria-label={`合并检查点 ${row.id}`}><p>{stages[row.status] || row.status} · v{row.version} · {row.kind === 'CHECKPOINT_RESTORE' ? '恢复操作' : '合并操作'}</p>
    <Button disabled={action.busy || !available} onClick={() => void action.run(async current => { report(undefined); setConfirmed(false); const value = await api.recovery(row); if (current()) setPreview(value); }, '仅核对写入记录与当前版本，尚未恢复。')}>核对检查点与当前结果</Button>
    {preview && <section aria-label="检查点恢复预览"><StatusMessage tone="warning">恢复会把所列章节保存为检查点内容的新版本，可能替换合并后的人工修改。先核对下面的当前内容。不会重新执行原合并。</StatusMessage>
      {preview.observations.map(item => <section key={item.chapter_id}><p>{item.chapter_id} · 检查点 v{item.checkpoint_version ?? '不存在'} / 当前 v{item.current_version ?? '不存在'} · {item.state}</p><div className="experimental-grid"><section><h5>操作前检查点 · {preview.checkpoint[item.chapter_id] ? preview.checkpoint[item.chapter_id]?.archived ? '已归档' : '有效章节' : '不存在'}</h5><RichNodes nodes={preview.checkpoint[item.chapter_id]?.document.content || []} /></section><section><h5>当前原稿 · {preview.current[item.chapter_id] ? preview.current[item.chapter_id]?.archived ? '已归档' : '有效章节' : '不存在'}</h5><RichNodes nodes={preview.current[item.chapter_id]?.document.content || []} /></section></div></section>)}
      <Details label="查看逐次写入意图与确认回执" value={preview.journal} />
      {!!preview.blocked.length && <StatusMessage tone="warning">当前不能恢复：{preview.blocked.join('、')}。请使用原编辑器的版本与恢复入口。</StatusMessage>}
      {!active && <p>这不是当前合并记录，只能核对。请从最新记录处理恢复。</p>}
      <label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={action.busy || !available || !active || !preview.can_restore} onChange={e => setConfirmed(e.target.checked)} />已核对当前内容，明确恢复此合并前检查点为新版本</label>
      <Button disabled={action.busy || !available || !active || !preview.can_restore || !confirmed} onClick={() => void action.run(async current => { report(undefined); try { await api.restore(row, preview); if (current()) report(undefined, '检查点已通过原版本服务恢复，历史与副本保留。'); } catch (error) { if (current()) report(error); } finally { if (current()) { setConfirmed(false); setPreview(undefined); refresh(); } } })}>确认恢复检查点</Button>
    </section>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
  </article>;
}
