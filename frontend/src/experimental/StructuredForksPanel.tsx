import { useEffect, useMemo, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import type { ForkChoice, ForkRecord } from './projectForksClient';
import { structuredForksClient, type StructuredComparison, type StructuredFork, type StructuredRecovery } from './structuredForksClient';
const kinds: Record<string, string> = { characters: '人物', locations: '地点', relationships: '人物关系' };
const fields: Record<string, string> = { name: '名称', status: '状态', record: '整条记录', current_location: '当前位置', source_character_id: '关系起点', target_character_id: '关系终点', goal: '目标', personality: '性格', description: '说明' };
const stages: Record<string, string> = { PREFLIGHT: '待确认分叉', FORKED: '分叉已建立', COMPLETED: '合并完成', RESTORED: '检查点已恢复', RECOVERY_REQUIRED: '需要恢复核对', APPLYING: '正在写入或结果待核对', CLAIMED: '已记录写入意图' };
type Api = ReturnType<typeof structuredForksClient>;
function valueText(value: unknown) { return value === null || value === undefined || value === '' ? '（空 / 不存在）' : typeof value === 'string' ? value : JSON.stringify(value, null, 2); }

export function StructuredForksPanel({ client, manuscriptForks = [] }: { client: ExperimentalClient; manuscriptForks?: ForkRecord[] }) {
  const api = useMemo(() => structuredForksClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]); const records = useResource(signal => api.records(signal), [api]);
  const action = useReviewAction(); const [selected, setSelected] = useState<string[]>([]); const [title, setTitle] = useState('');
  const [manuscriptId, setManuscriptId] = useState('');
  const manuscript = manuscriptForks.find(row => row.id === manuscriptId && row.status === 'FORKED' && row.target_available !== false);
  const [license, setLicense] = useState(''); const [permission, setPermission] = useState(false);
  const [operationError, setOperationError] = useState<unknown>(); const [receipt, setReceipt] = useState('');
  const report = (error: unknown, notice = '') => { setOperationError(error); setReceipt(notice); };
  const refresh = () => { catalog.reload(); records.reload(); setPermission(false); };
  const available = !catalog.loading && !catalog.error && !!catalog.data?.available;
  const sources = catalog.data?.records || []; const chosen = sources.filter(r => selected.includes(r.key));
  const missing = Array.from(new Set(chosen.flatMap(r => r.references.filter(ref => !selected.includes(ref.key)).map(ref => ref.key))));
  const ready = !records.loading && !records.error ? records.data : undefined;
  return <section className="experimental-section" aria-label="人物地点与关系分叉">
    <div className="experimental-actions"><h3>人物、地点与关系分叉</h3><Badge>原资料库 · 字段级三方审核</Badge><Button disabled={action.busy} onClick={refresh}>刷新结构分叉记录</Button></div>
    <p>所选记录可放入下方已建立的正文分叉，也可建立仅含结构记录的新项目，均通过原资料库保存。名称变化保持稳定 ID；人物位置与关系端点必须完整选择并映射。副本默认仅限本地，不继承云端许可或成员权限。</p>
    <StatusMessage>Canon、事件、Workflow 和未知嵌入字段暂不复制；含这些字段的记录会明确阻止。此范围不包括协作分支正文。归档保留原记录，跨资料库操作使用逐项记录，不能保证全局原子提交。</StatusMessage>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {catalog.data?.truncated && <StatusMessage tone="warning">每类资料最多展示 1000 条，本次列表不代表全部项目资料。</StatusMessage>}
    {!catalog.loading && !catalog.error && !available && <StatusMessage tone="warning">当前范围没有可用的原结构记录来源，不会读取基础项目作为协作分支内容。</StatusMessage>}
    {!!operationError && <ErrorMessage error={operationError} />}{receipt && <StatusMessage tone="success">{receipt}</StatusMessage>}
    <Panel title="选择原结构记录与复制许可">
      <Field label="结构记录目标"><select value={manuscriptId} disabled={action.busy} onChange={e => { setManuscriptId(e.target.value); setPermission(false); }}><option value="">新建仅含结构记录的本地项目</option>{manuscriptForks.filter(row => row.status === 'FORKED' && row.target_available !== false).map(row => <option key={row.id} value={row.id}>加入正文分叉：{row.title || row.target_id}</option>)}</select></Field>
      {manuscript && <StatusMessage>将资料加入正文分叉 {manuscript.title || manuscript.target_id}。只新增映射后的记录，不覆盖目标已有资料；正文与结构复制分两阶段，部分失败会保留两边记录与操作日志。</StatusMessage>}
      <Field label="结构分叉项目名称"><input value={title} disabled={action.busy} maxLength={160} onChange={e => setTitle(e.target.value)} /></Field>
      {available && !sources.length && <EmptyState title="没有可选结构记录" detail="先在原人物、地点或关系资料库保存记录。" />}
      {available && sources.map(row => <article key={row.key} className="experimental-record"><label className="experimental-check"><input type="checkbox" checked={selected.includes(row.key)} disabled={action.busy || !row.supported || !selected.includes(row.key) && selected.length >= 60} onChange={e => { setSelected(old => e.target.checked ? [...old, row.key] : old.filter(k => k !== row.key)); setPermission(false); }} />{kinds[row.kind]}：{row.title}</label>
        {!!row.references.length && <p>须一并选择：{row.references.map(r => r.key).join('、')}</p>}{!row.supported && <StatusMessage tone="warning">不支持当前记录：{row.reason}</StatusMessage>}<Details label={`查看来源摘要：${row.title}`} value={{ key: row.key, source_digest: row.source_digest }} /></article>)}
      {!!missing.length && <StatusMessage tone="warning">尚缺引用目标：{missing.join('、')}。请明确选择全部目标；不会静默复制其他资料。</StatusMessage>}
      <Field label="所选结构记录的许可说明"><input value={license} disabled={action.busy} maxLength={240} onChange={e => { setLicense(e.target.value); setPermission(false); }} /></Field>
      <label className="experimental-check"><input type="checkbox" checked={permission} disabled={action.busy || !license.trim() || !chosen.length} onChange={e => setPermission(e.target.checked)} />我有权将所选结构记录复制到此本地新项目</label>
      <Button disabled={action.busy || !available || !title.trim() || !permission || !chosen.length || chosen.length !== selected.length || !!missing.length || !!manuscriptId && !manuscript} onClick={() => void action.run(async current => { await api.preflight(title, chosen, license, manuscript ? { fork_id: manuscript.id, expected_version: manuscript.version } : undefined); if (current()) records.reload(); }, '已冻结所选记录、来源摘要、许可、ID 映射与目标，尚未写入资料。')}>仅预检结构分叉</Button>
      {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    </Panel>
    <Panel title="结构分叉与合并"><ResourceState loading={records.loading} error={records.error} empty={!!ready && !ready.items.length} />{ready?.items.map(row => <StructuredReview key={`${row.id}:${row.version}`} api={api} row={row} available={available} refresh={refresh} report={report} />)}</Panel>
    <Panel title="结构记录检查点与恢复">{ready && !ready.merges.length && <p>尚无结构合并检查点。</p>}{ready?.merges.map(row => <StructuredRecoveryReview key={`${row.id}:${row.version}`} api={api} row={row} active={ready.items.some(f => f.active_merge === row.id)} available={available} refresh={refresh} report={report} />)}</Panel>
  </section>;
}
type ReviewProps = { api: Api; row: StructuredFork; available: boolean; refresh: () => void; report: (error: unknown, notice?: string) => void };
function StructuredReview({ api, row, available, refresh, report }: ReviewProps) {
  const action = useReviewAction(); const [confirmed, setConfirmed] = useState(false); const [preview, setPreview] = useState<StructuredComparison>();
  const [choices, setChoices] = useState<Record<string, ForkChoice>>({}); const [dirty, setDirty] = useState(false); const [reviewed, setReviewed] = useState(false);
  useEffect(() => { if (!available) { setPreview(undefined); setReviewed(false); setConfirmed(false); } }, [available]);
  return <article className="experimental-record" aria-label={`结构分叉 ${row.title || row.id}`}>
    <strong>{row.title || row.id}</strong><Badge>{stages[row.status] || row.status} · v{row.version}</Badge><p>{row.manuscript_fork ? '已绑定正文分叉项目' : '新项目'}：{row.target_id} · 所选记录 {row.record_count}</p>{row.manuscript_fork && <StatusMessage>本次只向已审核的正文分叉加入所选结构记录。正文复制与资料复制分别保留操作日志。</StatusMessage>}
    {row.status === 'PREFLIGHT' && <><label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={action.busy || !available} onChange={e => setConfirmed(e.target.checked)} />已核对结构记录、映射与许可，创建此分叉</label><Button disabled={action.busy || !available || !confirmed} onClick={() => void action.run(async current => { report(undefined); try { await api.create(row); if (current()) report(undefined, '所选结构记录已通过原资料库复制。打开目标项目修改后，可返回这里逐字段比较。'); } catch (error) { if (current()) report(error); } finally { if (current()) refresh(); } })}>确认创建结构分叉</Button></>}
    {row.target_available === false && <StatusMessage tone="warning">副本项目当前不可访问；操作记录保留，不能比较副本内容。</StatusMessage>}
    {row.status === 'FORKED' && row.target_available !== false && <><Button disabled={action.busy || !available} onClick={() => void action.run(async current => { setReviewed(false); const next = await api.compare(row, choices); if (current()) { setPreview(next); setDirty(false); } })}>{preview ? '更新结构合并预览' : '比较结构记录三方差异'}</Button>
      {!!Object.keys(choices).length && <Button disabled={action.busy} onClick={() => { setChoices({}); setPreview(undefined); setReviewed(false); setDirty(false); }}>清除结构冲突选择</Button>}
      {preview && <section aria-label="结构三方合并预览"><p>待解决冲突 {preview.unresolved} 项 · 预计改写 {preview.write_count} 条原记录。应用时重新核对两端摘要与当前权限。</p>
        {preview.records.map(record => <section key={record.key}><h4>{kinds[record.kind]}：{record.title}</h4>{!record.changes.length && <p>此记录没有差异。</p>}{record.changes.map(change => <article key={change.id} className="experimental-record"><Badge tone={change.kind === 'CONFLICT' ? 'warning' : 'neutral'}>{fields[change.field] || change.field} · {change.kind === 'CONFLICT' ? '冲突：需选择' : change.kind === 'FORK_ONLY' ? '仅副本修改' : change.kind === 'ORIGINAL_ONLY' ? '仅原稿修改' : '双方一致'}</Badge>{change.reason === 'DELETE_OR_ARCHIVE_MODIFY' && <StatusMessage tone="warning">删除 / 归档与修改需要明确选择。原记录只会归档；活跃关系不可指向归档人物。</StatusMessage>}
          <div className="experimental-grid"><section><h5>结构基线</h5><p>{valueText(change.base)}</p></section><section><h5>当前原记录</h5><p>{valueText(change.ORIGINAL)}</p></section><section><h5>当前副本记录</h5><p>{valueText(change.FORK)}</p></section></div>
          {change.kind === 'CONFLICT' && <Field label={`${record.title} ${fields[change.field] || change.field} 结构冲突选择`}><select value={choices[change.id] || ''} disabled={action.busy} onChange={e => { const value = e.target.value as ForkChoice; setChoices(old => { const next = { ...old }; if (value) next[change.id] = value; else delete next[change.id]; return next; }); setDirty(true); setReviewed(false); }}><option value="">逐项选择</option><option value="ORIGINAL">保留原记录</option><option value="FORK">采用副本记录</option></select></Field>}
        </article>)}<Details label={`查看两端摘要：${record.title}`} value={{ original: record.original_digest, fork: record.fork_digest }} /></section>)}
        {preview.blocked.map((b, i) => <StatusMessage key={i} tone="warning">{b.key}：{b.code}。请先处理引用目标或关联记录，再重新比较。</StatusMessage>)}
        {dirty && <StatusMessage tone="warning">结构冲突选择已变化，请更新预览再确认。</StatusMessage>}
        <label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy || !available || dirty || !preview.can_apply} onChange={e => setReviewed(e.target.checked)} />已核对结构三方差异，建立检查点并合并</label>
        <Button disabled={action.busy || !available || dirty || !reviewed || !preview.can_apply || !preview.write_count} onClick={() => void action.run(async current => { report(undefined); try { await api.apply(row, preview, choices); if (current()) report(undefined, '结构记录已通过原资料库摘要校验合并，检查点和副本保留。'); } catch (error) { if (current()) report(error); } finally { if (current()) { setPreview(undefined); refresh(); } } })}>确认结构检查点并合并</Button>
      </section>}</>}
    {['CLAIMED', 'APPLYING', 'RECOVERY_REQUIRED'].includes(row.status) && <StatusMessage tone="warning">创建结果未知或部分完成。请核对原项目列表和记录，不会自动重试或覆盖副本。</StatusMessage>}
    <Details label="查看结构 ID 映射与来源许可" value={{ mapping: row.id_map, provenance: row.provenance, manuscript_fork: row.manuscript_fork }} />{!!row.journal?.length && <Details label="查看结构分叉写入记录" value={row.journal} />}
    {!!action.error && <ErrorMessage error={action.error} />}
  </article>;
}
function StructuredRecoveryReview({ api, row, active, available, refresh, report }: ReviewProps & { active: boolean }) {
  const action = useReviewAction(); const [preview, setPreview] = useState<StructuredRecovery>(); const [confirmed, setConfirmed] = useState(false);
  useEffect(() => { if (!available) { setPreview(undefined); setConfirmed(false); } }, [available]);
  return <article className="experimental-record"><p>{stages[row.status] || row.status} · v{row.version}</p><Button disabled={action.busy || !available} onClick={() => void action.run(async current => { setConfirmed(false); const result = await api.recovery(row); if (current()) setPreview(result); })}>核对结构检查点与当前记录</Button>
    {preview && <section aria-label="结构检查点恢复预览"><StatusMessage tone="warning">恢复会替换下列当前记录，保留更严格的隐私限制。未知写入只供核对，不自动重放。</StatusMessage>
      {Object.keys(preview.checkpoint).map(key => <section key={key}><h4>{key}</h4><div className="experimental-grid"><section><h5>结构检查点</h5><p>{valueText(preview.checkpoint[key])}</p></section><section><h5>当前结构记录</h5><p>{valueText(preview.current[key])}</p></section></div></section>)}
      <Details label="查看结构合并逐项写入记录" value={preview.journal} />{!!preview.blocked.length && <StatusMessage tone="warning">需原资料库恢复缺失记录：{preview.blocked.join('、')}</StatusMessage>}{!active && <p>仅最新合并记录可申请恢复。</p>}
      <label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={action.busy || !available || !active || !preview.can_restore} onChange={e => setConfirmed(e.target.checked)} />已核对当前结构记录，明确恢复此检查点</label>
      <Button disabled={action.busy || !available || !active || !preview.can_restore || !confirmed} onClick={() => void action.run(async current => { report(undefined); try { await api.restore(row, preview); if (current()) report(undefined, '结构检查点已通过原资料库重新保存。'); } catch (error) { if (current()) report(error); } finally { if (current()) { setPreview(undefined); refresh(); } } })}>确认恢复结构检查点</Button>
    </section>}{!!action.error && <ErrorMessage error={action.error} />}
  </article>;
}
