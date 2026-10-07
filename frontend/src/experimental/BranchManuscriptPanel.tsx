import { useMemo, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import type { WorkspaceNavigation } from './uxClient';

type Chapter = { id: string; title: string; version: number; novel_id: string; branch_id: string; origin?: { chapter_id: string; scope: { branch_id?: string } } };
type RecordRow = { id: string; status: string; version: number; preview_digest: string; source_scope?: object; target_scope?: object; sources?: object; id_map?: Record<string, string>; recovery?: object; source?: { version: number }; target?: { version: number } };
type Compare = { can_apply: boolean; preview_digest: string; source: { version: number }; target: { version: number }; conflicts: { id: string; reason?: string; base?: unknown; ORIGINAL?: unknown; FORK?: unknown }[]; segments: unknown[]; desired_document: unknown };
const base = '/branch-manuscript';
const enc = encodeURIComponent;
let instance = 0;

export function BranchManuscriptPanel({ client, onNavigate }: { client: ExperimentalClient; onNavigate?: (target: WorkspaceNavigation) => void }) {
  const key = useMemo(() => ++instance, [client]);
  return <BranchBody key={key} client={client} onNavigate={onNavigate} />;
}

function BranchBody({ client, onNavigate }: { client: ExperimentalClient; onNavigate?: (target: WorkspaceNavigation) => void }) {
  const catalog = useResource(signal => client.get<{ initialized: boolean; revision: number; chapter_count: number; can_write: boolean; can_review: boolean; capacity?: unknown }>(base + '/catalog', signal), [client]);
  const chapters = useResource(signal => client.get<{ items: Chapter[] }>(base + '/chapters', signal), [client]);
  const records = useResource(signal => client.get<{ forks: RecordRow[]; merges: RecordRow[] }>(base + '/records', signal), [client]);
  const action = useReviewAction();
  const [title, setTitle] = useState(''); const [sourceBranch, setSourceBranch] = useState('');
  const [sourceRows, setSourceRows] = useState<{ id: string; title: string; version: number }[]>();
  const [selected, setSelected] = useState<string[]>([]); const [selectedSourceBranch, setSelectedSourceBranch] = useState<string | null>(null);
  const [forkConfirmed, setForkConfirmed] = useState<string>();
  const [mergeChapter, setMergeChapter] = useState<Chapter>(); const [comparison, setComparison] = useState<Compare>();
  const [choices, setChoices] = useState<Record<string, 'ORIGINAL' | 'FORK'>>({});
  const [mergeConfirmed, setMergeConfirmed] = useState<string>();
  const [review, setReview] = useState<{ id: string; version: number; preview_digest: string; stale: boolean; desired_document: unknown; checkpoint: unknown }>();
  const readBlocked = catalog.loading || !!catalog.error || chapters.loading || !!chapters.error;
  const blocked = readBlocked || action.busy;
  const writable = !blocked && !!catalog.data?.can_write;
  const reviewable = !blocked && !!catalog.data?.can_review;
  const refresh = () => { catalog.reload(); chapters.reload(); records.reload(); setForkConfirmed(undefined); setMergeConfirmed(undefined); setComparison(undefined); setReview(undefined); };
  const compareBody = () => ({ chapter_id: mergeChapter!.id, target_chapter_id: mergeChapter!.origin!.chapter_id, target_branch_id: mergeChapter!.origin!.scope.branch_id || null, choices });
  const confirm = (row: RecordRow) => ({ expected_version: row.version, preview_digest: row.preview_digest, confirmed: true });
  return <section className="experimental-section" aria-label="协作分支正文">
    <div className="experimental-actions"><h3>协作分支正文</h3><Badge>独立正文 · CAS · 人工合并</Badge><Button disabled={action.busy} onClick={refresh}>刷新分支正文</Button></div>
    <p>分支有独立章节、正文版本和历史。未初始化的分支保持空白；只有明确分叉才复制已授权来源。写作和 AI 草稿仍使用原编辑器与审核入口。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!catalog.loading && !catalog.error && catalog.data && <StatusMessage>{catalog.data.initialized ? `分支已初始化 · revision ${catalog.data.revision}` : '此分支尚未初始化。创建章节或明确分叉后，分支正文才可用。'}</StatusMessage>}
    {!readBlocked && !!catalog.data?.capacity && <Details label="分支容量与恢复保留额度" value={catalog.data.capacity} />}
    {!blocked && !catalog.data?.can_write && <StatusMessage tone="warning">只读身份：创建、分叉和改写仍需正文写入权限。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    <Panel title="当前分支章节">
      <Field label="分支新章节标题"><input value={title} maxLength={300} disabled={!writable} onChange={e => setTitle(e.target.value)} /></Field>
      <Button disabled={!writable || !title.trim()} onClick={() => void action.run(async current => { await client.post(base + '/chapters', { title, content: '' }); if (current()) { setTitle(''); refresh(); } }, '已创建分支章节，可在原编辑器继续写作。')}>创建独立分支章节</Button>
      <ResourceState loading={chapters.loading} error={chapters.error} empty={!chapters.loading && !chapters.error && !chapters.data?.items.length} />
      {!readBlocked && chapters.data?.items.map(row => <article className="experimental-record" key={row.id}><strong>{row.title}</strong><Badge>v{row.version}</Badge>
        <Button disabled={!onNavigate} onClick={() => onNavigate?.({ kind: 'chapter', id: row.id, novel_id: row.novel_id, branch_id: row.branch_id, version: row.version, anchor: { offset: 0, scroll: 0 } })}>在原编辑器打开 {row.title}</Button>
        {row.origin && <Button disabled={!reviewable} onClick={() => { setMergeChapter(row); setComparison(undefined); setChoices({}); setMergeConfirmed(undefined); }}>比较并合并 {row.title}</Button>}
      </article>)}
    </Panel>
    <Panel title="明确选择来源并分叉">
      <p>主线来源需要项目级读取权限。分支角色本身不能读取或改写主线。</p>
      <Field label="来源分支 ID（留空为主线）"><input value={sourceBranch} maxLength={240} disabled={action.busy} onChange={e => { setSourceBranch(e.target.value); setSourceRows(undefined); setSelected([]); }} /></Field>
      <Button disabled={!writable} onClick={() => void action.run(async current => { const branch = sourceBranch.trim() || null; const result = await client.get<{ items: { id: string; title: string; version: number }[] }>(base + '/sources' + (branch ? '?source_branch_id=' + enc(branch) : '')); if (current()) { setSourceRows(result.items); setSelected([]); setSelectedSourceBranch(branch); } })}>读取已授权来源章节</Button>
      {!readBlocked && sourceRows && !sourceRows.length && <EmptyState title="来源没有可用章节" detail="选择另一个已授权来源，或先保存来源章节。" />}
      {!readBlocked && sourceRows?.map(row => <label className="experimental-check" key={row.id}><input type="checkbox" disabled={!writable} checked={selected.includes(row.id)} onChange={e => setSelected(old => e.target.checked ? [...old, row.id] : old.filter(id => id !== row.id))} />{row.title} · 来源 v{row.version}</label>)}
      <Button disabled={!writable || !selected.length || selected.length > 40} onClick={() => void action.run(async current => { await client.post(base + '/forks/preview', { chapter_ids: selected, source_branch_id: selectedSourceBranch }); if (current()) records.reload(); }, '来源版本已生成待审分叉记录，尚未复制正文。')}>建立分叉预检</Button>
      <ResourceState loading={records.loading} error={records.error} />
      {!readBlocked && !records.loading && !records.error && records.data?.forks.map(row => <article className="experimental-record" key={row.id}><Badge>{row.status} · v{row.version}</Badge><Details label="查看分叉来源、版本与章节映射" value={row} />
        {row.status === 'REVIEW' && <><label className="experimental-check"><input type="checkbox" checked={forkConfirmed === row.id} disabled={!writable} onChange={e => setForkConfirmed(e.target.checked ? row.id : undefined)} />已核对来源和版本，复制到当前分支</label>
          <Button disabled={!writable || forkConfirmed !== row.id} onClick={() => void action.run(async current => { await client.post(base + `/forks/${enc(row.id)}/apply`, confirm(row)); if (current()) refresh(); }, '分叉已保存为独立正文，主线保持原版本。')}>确认分叉到当前分支</Button>
          <Button disabled={!reviewable} onClick={() => void action.run(async current => { await client.post(base + `/fork/${enc(row.id)}/cancel`, { expected_version: row.version }); if (current()) refresh(); })}>取消分叉</Button></>}
      </article>)}
    </Panel>
    {!readBlocked && mergeChapter && <Panel title={`三方比较：${mergeChapter.title}`}>
      <p>比较分叉基线、当前来源和当前分支。来源写入权限及双方版本会在应用前再次检查。合并保留来源历史。</p>
      <Button disabled={!reviewable} onClick={() => void action.run(async current => { const result = await client.post<Compare>(base + '/compare', compareBody()); if (current()) { setComparison(result); setMergeConfirmed(undefined); } })}>更新三方比较</Button>
      {comparison && <><p>分支 v{comparison.source.version} / 来源 v{comparison.target.version} · 待解决冲突 {comparison.conflicts.length}</p>
        <Details label="查看完整富文本三方差异" value={comparison.segments} />
        {comparison.conflicts.map(conflict => <Field label={`冲突 ${conflict.id} 的人工选择`} key={conflict.id}><select value={choices[conflict.id] || ''} disabled={!reviewable} onChange={e => { setChoices(old => ({ ...old, [conflict.id]: e.target.value as 'ORIGINAL' | 'FORK' })); setComparison(undefined); }}><option value="">请选择</option><option value="ORIGINAL">保留当前来源</option><option value="FORK">采用当前分支</option></select></Field>)}
        {comparison.can_apply && <><Details label="查看将写入来源的完整正文" value={comparison.desired_document} /><Button disabled={!reviewable} onClick={() => void action.run(async current => { await client.post(base + '/merges', { ...compareBody(), preview_digest: comparison.preview_digest }); if (current()) { records.reload(); setComparison(undefined); } }, '已保存人工合并提案，尚未改写来源。')}>保存此合并提案供确认</Button></>}
      </>}
    </Panel>}
    <Panel title="合并审核与中断核对">
      <p>应用前记录写入意图。遇到结果未知或重启，先核对持久回执和当前版本，不自动重复合并。主线缺少精确操作回执时保持需要人工恢复。</p>
      {!readBlocked && !records.loading && !records.error && records.data?.merges.map(row => <article className="experimental-record" key={row.id}><Badge>{row.status} · v{row.version}</Badge><Details label="查看合并版本、权限范围与恢复证据" value={row} />
        {row.status === 'REVIEW' && <><Button disabled={!reviewable} onClick={() => void action.run(async current => { const result = await client.get<any>(base + `/merges/${enc(row.id)}/review`); if (current()) { setReview(result); setMergeConfirmed(undefined); } })}>读取此提案正文与当前来源</Button>{review?.id === row.id && <><Details label="查看提案将写入的正文与原始检查点" value={review} />{review.stale && <StatusMessage tone="warning">来源已经改变，此提案不能应用。请取消并重新比较。</StatusMessage>}</>}<label className="experimental-check"><input type="checkbox" disabled={!reviewable || review?.id !== row.id || review.version !== row.version || review.stale} checked={mergeConfirmed === row.id} onChange={e => setMergeConfirmed(e.target.checked ? row.id : undefined)} />确认采用已审核正文并改写指定来源</label><Button disabled={!reviewable || mergeConfirmed !== row.id || review?.id !== row.id || review.version !== row.version || review.stale} onClick={() => void action.run(async current => { try { await client.post(base + `/merges/${enc(row.id)}/apply`, confirm(row)); } finally { if (current()) refresh(); } }, '已通过指定正文所有者保存合并新版本。')}>确认人工合并</Button><Button disabled={!reviewable} onClick={() => void action.run(async current => { await client.post(base + `/merge/${enc(row.id)}/cancel`, { expected_version: row.version }); if (current()) refresh(); })}>取消合并提案</Button></>}
        {['APPLYING', 'RECOVERY_REQUIRED'].includes(row.status) && <Button disabled={!reviewable} onClick={() => void action.run(async current => { await client.post(base + `/merges/${enc(row.id)}/recovery`, { expected_version: row.version }); if (current()) records.reload(); }, '已核对当前来源与持久回执，没有重放写入。')}>核对中断合并结果</Button>}
      </article>)}
    </Panel>
  </section>;
}
