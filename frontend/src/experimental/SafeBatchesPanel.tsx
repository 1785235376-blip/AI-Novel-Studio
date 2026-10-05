import { useEffect, useMemo, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { safeBatchesClient, type BatchInput, type BatchRecord } from './safeBatchesClient';
import { downloadPortableBlob } from './portableProjectsClient';
let nextScope = 0;
export function SafeBatchesPanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++nextScope, [client]); return <SafeBatchesContent key={identity} client={client} />;
}
function SafeBatchesContent({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => safeBatchesClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]); const records = useResource(signal => api.list(signal), [api]);
  const action = useReviewAction(); const stop = useReviewAction(); const [chapters, setChapters] = useState<string[]>([]);
  const [proof, setProof] = useState(true); const [exporting, setExporting] = useState(false); const [format, setFormat] = useState('txt'); const [brief, setBrief] = useState(''); const [skip, setSkip] = useState(true);
  const [start, setStart] = useState(''); const [end, setEnd] = useState('');
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({}); const [proposalReviewed, setProposalReviewed] = useState<Record<string, boolean>>({});
  const [preview, setPreview] = useState<{ id: string; url: string }>();
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  const available = !catalog.loading && !catalog.error && !!catalog.data; const recordsAvailable = !records.loading && !records.error && !!records.data;
  const refresh = () => { setReviewed({}); setProposalReviewed({}); setPreview(undefined); catalog.reload(); records.reload(); };
  const selectedBrief = available ? catalog.data!.briefs.find(b => b.id === brief) : undefined;
  const reload = () => { setReviewed({}); setProposalReviewed({}); records.reload(); };
  const execute = (row: BatchRecord) => void action.run(async current => { try { await api.dispatch(row); } finally { if (current()) records.reload(); } }, '本阶段完成。不会自动开始下一项。');
  return <section className="experimental-section" aria-label="安全批处理与执行预检">
    <div className="experimental-actions"><h3>安全批处理与执行预检</h3><Badge>并发上限 1 · 费用上限 0 USD</Badge><Button disabled={records.loading || catalog.loading} onClick={refresh}>刷新批次状态</Button></div>
    <p>先预检，再确认当前快照与预算，最后逐阶段执行。仅支持本地确定性校对、原导出器和已注册的合成媒体测试；没有模型或云端自动启动。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对本机会话、分支权限及批处理与阅读预检开关。草稿选择仍保留；权限恢复后可刷新。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{!!stop.error && <ErrorMessage error={stop.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}{stop.notice && <StatusMessage tone="warning">{stop.notice}</StatusMessage>}
    <Panel title="选择本次批次范围">
      {available && !catalog.data!.chapters.length && <EmptyState title="没有可用章节" detail="先保存正文；无授权或缺少分支读取适配器时不会借用主分支。" />}
      {available && catalog.data!.chapters.map(c => <label className="experimental-check" key={c.id}><input type="checkbox" checked={chapters.includes(c.id)} disabled={action.busy} onChange={() => setChapters(ids => ids.includes(c.id) ? ids.filter(id => id !== c.id) : [...ids, c.id])} />{c.title} · v{c.version}</label>)}
      <label className="experimental-check"><input type="checkbox" checked={proof} disabled={action.busy} onChange={e => setProof(e.target.checked)} />逐章确定性校对（不自动改文）</label>
      {proof && chapters.length === 1 && <><Field label="校对起点（Unicode 字符偏移，可留空）"><input type="number" min="0" max="2000000" value={start} disabled={action.busy} onChange={e => setStart(e.target.value)} /></Field><Field label="校对终点（Unicode 字符偏移，可留空）"><input type="number" min="1" max="2000000" value={end} disabled={action.busy} onChange={e => setEnd(e.target.value)} /></Field><p>留空表示整章；范围采用与阅读区相同的 Unicode 字符坐标，emoji 按一个字符计。仅核对完全落在范围内的发现。</p></>}
      <label className="experimental-check"><input type="checkbox" checked={exporting} disabled={action.busy} onChange={e => setExporting(e.target.checked)} />导出所选章节</label>
      <Field label="批次导出格式"><select value={format} disabled={action.busy || !available || !exporting} onChange={e => setFormat(e.target.value)}>{(catalog.data?.formats || ['txt']).map(f => <option value={f} key={f}>{f.toUpperCase()}</option>)}</select></Field>
      <Field label="合成媒体来源简报"><select value={brief} disabled={action.busy || !available} onChange={e => setBrief(e.target.value)}><option value="">不生成媒体</option>{available && catalog.data!.briefs.map(b => <option key={b.id} value={b.id}>{b.title} · v{b.version}</option>)}</select></Field>
      <p>合成媒体生成固定测试图片，用于核验流程。真实音频重做、图像与视频模型需要原工作流和 Broker 成本准入，目前不可在此执行；GPU 占用未知，不调度外部进程。</p>
      <label className="experimental-check"><input type="checkbox" checked={skip} disabled={action.busy} onChange={e => setSkip(e.target.checked)} />跳过同一来源与参数下已完成的校对和导出结果</label>
      <Button disabled={action.busy || !available || ((!chapters.length || (!proof && !exporting)) && !selectedBrief) || chapters.length > 19 || chapters.some(id => !catalog.data!.chapters.some(c => c.id === id))} onClick={() => void action.run(async current => {
        const items: BatchInput[] = [];
        if (proof) chapters.forEach(id => items.push({ kind: 'PROOF', chapter_ids: [id], ...(chapters.length === 1 && (start || end) ? { start: Number(start || 0), end: end ? Number(end) : null } : {}) }));
        if (exporting && chapters.length) items.push({ kind: 'EXPORT', chapter_ids: chapters, format });
        if (selectedBrief) items.push({ kind: 'SYNTHETIC_MEDIA', brief_id: selectedBrief.id, expected_brief_version: selectedBrief.version, adapter_id: 'mock-image-v1' });
        await api.preflight(items, skip); if (current()) reload();
      }, '已保存只读执行预检。请核对当前来源、权限与零费用预算后确认。')}>仅预检所选批次</Button>
    </Panel>
    <Panel title="批次快照与阶段结果">
      <ResourceState loading={records.loading} error={records.error} empty={recordsAvailable && !records.data!.items.length} />
      {recordsAvailable && records.data!.items.map(row => <article className="experimental-record" key={row.id} aria-label={`批次 ${row.id}`}>
        <div className="experimental-actions"><strong>批次 {row.id}</strong><Badge>{row.status} · v{row.version}</Badge></div>
        {row.stale ? <StatusMessage tone="warning">来源、规则或预算配置已变化。旧内容已隐藏；请按当前选择重新预检。</StatusMessage> : <>
          <p>快照摘要：{row.snapshot_digest}；已知费用 0 USD；执行并发上限 1。</p>
          {row.items?.map(item => <div key={item.index} className="experimental-record"><div className="experimental-actions"><strong>阶段 {item.index + 1} · {item.kind}</strong><Badge>{item.status} · {item.attempts} 次尝试</Badge></div>
            <p>输入章节：{item.chapter_ids.join('、') || '已校验媒体简报'}；所需权限：{item.permission}</p>
            <Details value={{ versions: item.source_versions, parameters: item.configuration_summary }} label="核对来源版本与本阶段参数" />
            {item.error_code && <StatusMessage tone="warning">{item.error_code}。先核对原任务与当前权限；结果未知时不会重放。</StatusMessage>}
            {item.findings && <Details value={item.findings} label="查看真实校对发现" />}
            {item.download_available && <Button disabled={action.busy} onClick={() => void action.run(async current => { const blob = await api.download(row, item.index); if (current()) downloadPortableBlob(blob, `batch-export.${item.format === 'markdown' ? 'md' : item.format}`); })}>下载阶段 {item.index + 1} 导出文件</Button>}
            {item.proposals?.map(p => <div key={p.id}><p>合成候选：{p.verification} · {p.status} · {p.media.width} × {p.media.height}</p>
              <Button disabled={action.busy} onClick={() => void action.run(async current => { const blob = await api.preview(row, p); if (current()) setPreview({ id: p.id, url: URL.createObjectURL(blob) }); })}>预览合成候选</Button>
              {preview?.id === p.id && <img src={preview.url} alt="实际解码的合成媒体候选" />}
              {p.status !== 'APPROVED' && <><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={!!proposalReviewed[p.id]} onChange={e => setProposalReviewed(v => ({ ...v, [p.id]: e.target.checked }))} />已预览并确认将此合成候选登记为正式资产</label>
                <Button disabled={action.busy || !proposalReviewed[p.id] || preview?.id !== p.id || row.status === 'CANCELLED'} onClick={() => void action.run(async current => { await api.approve(row, p); if (current()) reload(); }, '已通过原媒体审核服务登记本候选，未重复接受其他结果。')}>确认接受此合成候选</Button></>}
            </div>)}
          </div>)}
          {row.status === 'PREFLIGHT' && <><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={!!reviewed[row.id]} onChange={e => setReviewed(v => ({ ...v, [row.id]: e.target.checked }))} />已核对本批次来源版本、权限、资源与 0 USD 预算</label>
            <Button disabled={action.busy || !reviewed[row.id]} onClick={() => void action.run(async current => { await api.confirm(row); if (current()) reload(); }, '当前快照已确认，尚未执行。请点击执行下一阶段。')}>确认此批次快照与预算</Button></>}
          {['READY', 'PARTIAL'].includes(row.status) && row.items?.some(i => i.status === 'PENDING') && <Button disabled={action.busy} onClick={() => execute(row)}>执行下一阶段</Button>}
          {row.status === 'PARTIAL' && row.items?.some(i => i.status === 'FAILED') && <Button disabled={action.busy} onClick={() => void action.run(async current => { await api.retry(row); if (current()) reload(); }, '仅失败项已返回预检。已完成结果保留，重试前需要重新确认。')}>仅预检失败项重试</Button>}
          {row.status === 'UNKNOWN' && <StatusMessage tone="warning">原执行结果未知。请先核对原任务和成本记录；本入口不自动重放，也不会把未知结果当作未收费。</StatusMessage>}
        </>}
        {!['COMPLETED', 'CANCELLED'].includes(row.status) && <Button disabled={stop.busy} onClick={() => void stop.run(async current => { const fresh = (await api.list()).items.find(b => b.id === row.id); if (!current() || !fresh) return; await api.stop(fresh); if (current()) records.reload(); }, '已停止批次后续阶段。正在返回的本地结果将被丢弃；已完成成果保留。')}>停止此批次后续阶段</Button>}
      </article>)}
    </Panel>
  </section>;
}
