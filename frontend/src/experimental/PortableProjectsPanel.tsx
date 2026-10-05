import { useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { portableProjectsClient, readPortableFile, downloadPortableBlob } from './portableProjectsClient';
let nextScope = 0;
const conflicts: Record<string, string> = { DIGEST_MISMATCH: '候选文件与原媒体摘要不同；确认替代后才会写入。', ORIGINAL_DIGEST_UNKNOWN: '原媒体摘要未知；不能证明候选文件与原文件相同。', SOURCE_CHANGED: '章节版本或来源权限已变化；请重新预检。', ORIGINAL_REFERENCE_CHANGED: '原媒体状态或摘要已变化；请重新预检。', PREFLIGHT_REQUIRED: '此旧记录缺少完整影响报告；请重新预检。' };
const names: Record<string, string> = { MANUSCRIPT: '作品正文', ACCEPTED_ASSETS: '正式资产', HISTORY: '历史版本', TRASH: '回收站', REPRODUCIBLE_CACHE: '可重建缓存', TEMPORARY_FAILED_FILES: '临时失败与恢复文件' };
export function PortableProjectsPanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++nextScope, [client]); return <PortableProjectsContent key={identity} client={client} />;
}
function PortableProjectsContent({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => portableProjectsClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]); const records = useResource(signal => api.records(signal), [api]); const storage = useResource(signal => api.storage(signal), [api]);
  const action = useReviewAction(); const [selected, setSelected] = useState<string[]>([]); const [file, setFile] = useState<File>();
  const [relinkFile, setRelinkFile] = useState<File>(); const [missing, setMissing] = useState(''); const [kind, setKind] = useState('audio');
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({}); const [replace, setReplace] = useState<Record<string, boolean>>({}); const [cleanupReviewed, setCleanupReviewed] = useState(false); const epoch = useRef(0);
  const available = !catalog.loading && !catalog.error && !!catalog.data; const recordAvailable = !records.loading && !records.error && !!records.data; const storageAvailable = !storage.loading && !storage.error && !!storage.data;
  const refresh = () => { epoch.current++; setReviewed({}); setReplace({}); setCleanupReviewed(false); catalog.reload(); records.reload(); storage.reload(); };
  const chosenMissing = available ? catalog.data!.missing.find(r => r.id === missing) : undefined;
  return <section className="experimental-section" aria-label="项目便携与资源恢复">
    <div className="experimental-actions"><h3>项目便携与资源恢复</h3><Badge>新项目副本 · 明确确认</Badge><Button disabled={action.busy} onClick={refresh}>刷新便携与存储状态</Button></div>
    <p>便携包包含选中的当前正文与安全媒体，不包含历史、回收站、Canon 或 Workflow。完整恢复请使用原离线备份。凭据、模型与权限不会随包复制。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对本机会话、当前分支权限和便携功能开关。所选文件仍保留，可刷新重试。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    <Panel title="导出选中的当前正文">
      {available && !catalog.data!.chapters.length && <EmptyState title="没有已授权章节" detail="先保存正文，或切换到可读取的分支。" />}
      {available && catalog.data!.chapters.map(chapter => <label className="experimental-check" key={chapter.id}><input type="checkbox" checked={selected.includes(chapter.id)} disabled={action.busy} onChange={() => setSelected(ids => ids.includes(chapter.id) ? ids.filter(id => id !== chapter.id) : [...ids, chapter.id])} />{chapter.title} · v{chapter.version}</label>)}
      <Button disabled={action.busy || !available || !selected.length || selected.some(id => !catalog.data!.chapters.some(c => c.id === id))} onClick={() => void action.run(async current => { await api.export(selected); if (current()) { records.reload(); storage.reload(); } }, '已生成带摘要校验的便携包，可在下方下载。')}>创建所选章节便携包</Button>
    </Panel>
    <Panel title="导入预检与新项目恢复">
      <Field label="选择便携 ZIP 文件"><input type="file" accept=".zip,application/zip" disabled={action.busy} onChange={e => { epoch.current++; setFile(e.target.files?.[0]); setReviewed({}); }} /></Field>
      {file && <p>已选择：{file.name} · {file.size} 字节</p>}
      <p>最多 40 MiB；单媒体最多 8 MiB；只恢复到应用管理的新项目目录。缺素材仍保留正文，恢复前列出缺项。</p>
      {available && !catalog.data!.restore_available && <StatusMessage tone="warning">当前协作分支缺少新项目创建授权适配器；可预检，不能恢复或改写分支。</StatusMessage>}
      <Button disabled={action.busy || !available || !file || !/\.zip$/i.test(file.name) || file.size > 40 * 1024 * 1024} onClick={() => void action.run(async current => { const ticket = epoch.current; const chosen = file!; const bytes = await readPortableFile(chosen); if (!current() || ticket !== epoch.current) return; await api.preflight(chosen.name, bytes); if (current()) records.reload(); }, '文件校验完成。请核对缺项并另行确认恢复；还没有创建项目。')}>仅预检便携包</Button>
    </Panel>
    <Panel title="按摘要或人工选择重连缺失媒体">
      {available && !catalog.data!.missing.length && <p>当前已授权正文没有可重连的缺失媒体。</p>}
      <Field label="缺失媒体引用"><select value={missing} disabled={action.busy || !available} onChange={e => { setMissing(e.target.value); setReviewed({}); }}><option value="">选择缺失引用</option>{available && catalog.data!.missing.map(r => <option key={r.id} value={r.id}>{r.id} · {r.expected_sha256 ? '有原摘要' : '原摘要未知'}</option>)}</select></Field>
      <Field label="重连媒体类型"><select value={kind} disabled={action.busy} onChange={e => setKind(e.target.value)}><option value="audio">音频</option><option value="image">图片</option><option value="video">视频</option></select></Field>
      <Field label="选择重连媒体文件"><input type="file" disabled={action.busy} onChange={e => { epoch.current++; setRelinkFile(e.target.files?.[0]); setReviewed({}); }} /></Field>
      {relinkFile && <p>已选择重连文件：{relinkFile.name}</p>}
      <Button disabled={action.busy || !chosenMissing || !relinkFile || relinkFile.size > 8 * 1024 * 1024} onClick={() => void action.run(async current => { const ticket = epoch.current; const chosen = relinkFile!; const bytes = await readPortableFile(chosen, 8 * 1024 * 1024); if (!current() || ticket !== epoch.current) return; await api.preflightRelink(chosen.name, bytes, chosenMissing!.id, chosenMissing!.chapter_ids, kind); if (current()) records.reload(); }, '重连文件已解码并校验摘要，尚未替换引用。')}>仅校验重连文件</Button>
      <p>不会按同名文件猜测匹配。摘要不同或未知时需要明确选择替代；改写引用通过原章节版本服务并保留历史。</p>
    </Panel>
    <Panel title="便携与重连记录">
      <ResourceState loading={records.loading} error={records.error} empty={recordAvailable && !records.data!.items.length} />
      {recordAvailable && records.data!.items.map(row => <article key={row.id} className="experimental-record"><div className="experimental-actions"><strong>{row.title || (row.kind === 'RELINK' ? '媒体重连预检' : '便携包')}</strong><Badge>{row.status} · v{row.version}</Badge></div>
        {row.chapter_count != null && <p>{row.chapter_count} 个章节；缺失媒体 {row.media?.filter(m => m.state === 'MISSING').length || 0} 项</p>}
        {!!row.media?.some(media => media.state === 'MISSING') && <Details value={row.media.filter(media => media.state === 'MISSING')} label="查看缺失媒体清单" />}
        {row.kind === 'EXPORT' && <Button disabled={action.busy} onClick={() => void action.run(async current => { const blob = await api.download(row); if (current()) downloadPortableBlob(blob, 'portable-project.zip'); })}>下载便携 ZIP</Button>}
        {row.kind === 'RELINK' && row.relink_review && <div aria-label="重连影响与冲突报告">
          <p>缺失引用：{row.relink_review.missing_id}</p>
          <Field label="原媒体 SHA-256"><input readOnly value={row.relink_review.expected_sha256 || '未知'} /></Field>
          <Field label="候选文件 SHA-256"><input readOnly value={row.relink_review.candidate_sha256} /></Field>
          <p>本次改写 {row.relink_review.affected_chapters.length} 个章节的当前引用；历史版本和原资产保留。</p>
          <ul>{row.relink_review.affected_chapters.map(chapter => <li key={chapter.id}>{chapter.title} · 预检 v{chapter.version}{chapter.current_version != null && <> · 当前 v{chapter.current_version}</>}</li>)}</ul>
          {row.relink_review.conflicts.map((conflict, index) => <StatusMessage key={index} tone="warning">{conflicts[conflict.code] || conflict.code}</StatusMessage>)}
          {!row.relink_review.conflicts.length && <p>预检未发现摘要或章节版本冲突。</p>}
        </div>}
        {row.status === 'PREFLIGHT' && <>
          {row.kind === 'RELINK' && <StatusMessage tone={row.digest_matches ? 'success' : 'warning'}>{row.digest_matches ? '内容摘要与原媒体一致。' : '内容摘要不同或原摘要未知，需要人工确认替代。'}</StatusMessage>}
          <label className="experimental-check"><input type="checkbox" checked={!!reviewed[row.id]} disabled={action.busy} onChange={e => setReviewed(v => ({ ...v, [row.id]: e.target.checked }))} />已核对本记录与缺失项，确认{row.kind === 'IMPORT' ? '创建新项目副本' : '重连所列章节引用'}</label>
          {row.kind === 'RELINK' && !row.digest_matches && <label className="experimental-check"><input type="checkbox" checked={!!replace[row.id]} disabled={action.busy} onChange={e => setReplace(v => ({ ...v, [row.id]: e.target.checked }))} />明确使用内容不同或摘要未知的替代文件</label>}
          <Button disabled={action.busy || !available || !catalog.data!.restore_available || !reviewed[row.id] || row.relink_review?.can_confirm === false || (row.kind === 'RELINK' && !row.digest_matches && !replace[row.id])} onClick={() => void action.run(async current => { try { if (row.kind === 'IMPORT') await api.restore(row); else await api.relink(row, !!replace[row.id]); } finally { if (current()) refresh(); } }, row.kind === 'IMPORT' ? '恢复完成。新项目 ID 显示在记录中，请返回项目列表打开。' : '引用已更新，旧资产和历史仍保留。')}>{row.kind === 'IMPORT' ? '确认恢复到新项目' : '确认重连当前引用'}</Button>
        </>}
        {row.target_id && <p>新项目 ID：{row.target_id}</p>}
        {row.status === 'RECOVERY_REQUIRED' && <StatusMessage tone="warning">操作部分完成或结果无法确认。已保留新项目、原文件和映射；不会自动重复写入。请在原项目与版本入口核对。</StatusMessage>}
        {row.id_map && <Details value={row.id_map} label="查看新旧引用映射" />}
      </article>)}
    </Panel>
    <Panel title="存储分类与清理预览">
      <ResourceState loading={storage.loading} error={storage.error} />
      {storageAvailable && <><ul>{storage.data!.categories.map(c => <li key={c.kind}>{names[c.kind] || c.kind}：{c.bytes == null ? '未统计，保留' : `${c.bytes} 字节`}{c.cleanable ? '（可重建便携缓存）' : '（不清理）'}{!!c.unmeasured_records && `；另有 ${c.unmeasured_records} 项无法校验，保留且未计入`}</li>)}</ul>
        <p>正文与历史按当前已授权章节的内容字节计量；正式资产按登记大小计量。恢复输入只统计当前用户可校验的保留文件与待确认资产，不代表整个磁盘占用。</p>
        <Details value={storage.data!.eligible} label="查看本次可清理缓存清单" />
        <p>本次可清理 {storage.data!.eligible.length} 个经过校验、未被任务占用的导出缓存；历史、回收站、正式资产和恢复输入保留。</p>
        <label className="experimental-check"><input type="checkbox" checked={cleanupReviewed} disabled={action.busy} onChange={e => setCleanupReviewed(e.target.checked)} />已核对当前预览，只清理列出的可重建缓存</label>
        <Button disabled={action.busy || !cleanupReviewed || !storage.data!.eligible.length} onClick={() => void action.run(async current => { const preview = storage.data!; await api.cleanup(preview, preview.eligible.map(c => c.id)); if (current()) refresh(); }, '已清理确认的导出缓存；原正文、历史、回收站和资产未修改。')}>确认清理预览中的缓存</Button>
      </>}
    </Panel>
  </section>;
}
