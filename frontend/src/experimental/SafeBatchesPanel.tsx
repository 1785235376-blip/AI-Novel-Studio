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
  const [brokerPreview, setBrokerPreview] = useState(''); const [preset, setPreset] = useState(''); const [voiceIds, setVoiceIds] = useState<string[]>([]); const [audioBroker, setAudioBroker] = useState('');
  const [start, setStart] = useState(''); const [end, setEnd] = useState('');
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({}); const [proposalReviewed, setProposalReviewed] = useState<Record<string, boolean>>({});
  const [preview, setPreview] = useState<{ id: string; url: string; audio?: boolean }>();
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  const available = !catalog.loading && !catalog.error && !!catalog.data; const recordsAvailable = !records.loading && !records.error && !!records.data;
  const refresh = () => { setReviewed({}); setProposalReviewed({}); setPreview(undefined); catalog.reload(); records.reload(); };
  const selectedBrief = available ? catalog.data!.briefs.find(b => b.id === brief) : undefined;
  const selectedBroker = available ? catalog.data!.broker_previews?.find(p => p.id === brokerPreview) : undefined;
  const selectedAudioBroker = available ? catalog.data!.broker_previews?.find(p => p.id === audioBroker && p.capability === 'AUDIO') : undefined;
  const selectedVoices = available ? catalog.data!.voice_jobs?.filter(j => voiceIds.includes(j.id)) || [] : [];
  const itemCount = (proof ? chapters.length : 0) + (exporting && chapters.length ? 1 : 0) + (selectedBrief ? 1 : 0) + selectedVoices.length;
  const selectedPreset = available ? catalog.data!.presets?.find(p => p.id === preset) : undefined;
  const reload = () => { setReviewed({}); setProposalReviewed({}); records.reload(); };
  const execute = (row: BatchRecord) => void action.run(async current => { try { await api.dispatch(row); } finally { if (current()) records.reload(); } }, '本阶段完成。不会自动开始下一项。');
  return <section className="experimental-section" aria-label="安全批处理与执行预检">
    <div className="experimental-actions"><h3>安全批处理与执行预检</h3><Badge>并发上限 1 · 费用上限 0 USD</Badge><Button disabled={records.loading || catalog.loading} onClick={refresh}>刷新批次状态</Button></div>
    <p>先预检，再确认当前快照与预算，最后逐阶段执行。复用本地校对、原导出器与媒体工作流。真实注册适配器还需原 Broker 的同一来源、明确零费用预检；没有云端自动启动。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对本机会话、分支权限及批处理与阅读预检开关。草稿选择仍保留；权限恢复后可刷新。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{!!stop.error && <ErrorMessage error={stop.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}{stop.notice && <StatusMessage tone="warning">{stop.notice}</StatusMessage>}
    <Panel title="选择本次批次范围">
      <Field label="本项目批处理参数模板"><select value={preset} disabled={action.busy || !available} onChange={e => { const chosen = catalog.data?.presets?.find(p => p.id === e.target.value); setPreset(e.target.value); if (chosen) { setProof(chosen.content.proof); setExporting(!!chosen.content.export_format); if (chosen.content.export_format) setFormat(chosen.content.export_format); setSkip(chosen.content.skip_satisfied); } }}><option value="">手工参数</option>{catalog.data?.presets?.map(p => <option key={p.id} value={p.id}>{p.title} · v{p.version}</option>)}</select></Field>
      <p>模板来自 B01 本项目副本，可在模板库比较和回退。模板只复用参数；来源、审批、预算与执行仍需本次核对。</p>
      {available && !catalog.data!.chapters.length && <EmptyState title="没有可用章节" detail="先保存正文；无授权或缺少分支读取适配器时不会借用主分支。" />}
      {available && catalog.data!.chapters.map(c => <label className="experimental-check" key={c.id}><input type="checkbox" checked={chapters.includes(c.id)} disabled={action.busy} onChange={() => setChapters(ids => ids.includes(c.id) ? ids.filter(id => id !== c.id) : [...ids, c.id])} />{c.title} · v{c.version}</label>)}
      <label className="experimental-check"><input type="checkbox" checked={proof} disabled={action.busy || !!selectedPreset} onChange={e => setProof(e.target.checked)} />逐章确定性校对（不自动改文）</label>
      {proof && chapters.length === 1 && <><Field label="校对起点（Unicode 字符偏移，可留空）"><input type="number" min="0" max="2000000" value={start} disabled={action.busy} onChange={e => setStart(e.target.value)} /></Field><Field label="校对终点（Unicode 字符偏移，可留空）"><input type="number" min="1" max="2000000" value={end} disabled={action.busy} onChange={e => setEnd(e.target.value)} /></Field><p>留空表示整章；范围采用与阅读区相同的 Unicode 字符坐标，emoji 按一个字符计。仅核对完全落在范围内的发现。</p></>}
      <label className="experimental-check"><input type="checkbox" checked={exporting} disabled={action.busy || !!selectedPreset} onChange={e => setExporting(e.target.checked)} />导出所选章节</label>
      <Field label="批次导出格式"><select value={format} disabled={action.busy || !available || !exporting || !!selectedPreset} onChange={e => setFormat(e.target.value)}>{(catalog.data?.formats || ['txt']).map(f => <option value={f} key={f}>{f.toUpperCase()}</option>)}</select></Field>
      <Field label="媒体来源简报"><select value={brief} disabled={action.busy || !available} onChange={e => setBrief(e.target.value)}><option value="">不生成媒体</option>{available && catalog.data!.briefs.map(b => <option key={b.id} value={b.id}>{b.title} · v{b.version}</option>)}</select></Field>
      <Field label="原 Broker 媒体准入预检"><select value={brokerPreview} disabled={action.busy || !available || !selectedBrief} onChange={e => setBrokerPreview(e.target.value)}><option value="">仅使用固定合成图片测试</option>{catalog.data?.broker_previews?.filter(p => p.capability !== 'AUDIO').map(p => <option key={p.id} value={p.id}>{p.adapter_id} · {p.cost_state} · {p.id}</option>)}</select></Field>
      <p>真实媒体先在模型路由中选择 IMAGE、同一来源、本地与 0 USD 上限。这里只接受仍有效的原准入预检，结果未知时保留原账本记录。外部 GPU 占用未知，不调度外部进程；真实质量待验。</p>
      <Field label="原 Broker 语音准入预检"><select value={audioBroker} disabled={action.busy || !available} onChange={e => { setAudioBroker(e.target.value); setVoiceIds([]); }}><option value="">不重做语音</option>{catalog.data?.broker_previews?.filter(p => p.capability === 'AUDIO').map(p => <option key={p.id} value={p.id}>{p.audio_provider_id} / {p.model_id} · {p.cost_state}</option>)}</select></Field>
      {selectedAudioBroker && <fieldset><legend>选择已在声音导演审核并排队的语音段</legend>{catalog.data?.voice_jobs?.filter(j => selectedAudioBroker.source_ids.includes(j.chapter_id) && j.provider_id === selectedAudioBroker.audio_provider_id && j.model_id === selectedAudioBroker.model_id).map(j => <label className="experimental-check" key={j.id}><input type="checkbox" checked={voiceIds.includes(j.id)} disabled={action.busy} onChange={() => setVoiceIds(ids => ids.includes(j.id) ? ids.filter(id => id !== j.id) : [...ids, j.id])} />{j.segment_id} · {j.status} · {j.approval_status}</label>)}</fieldset>}
      <p>语音只接续原声音导演已批准的任务，不重新执行已满意或锁定的片段。原价格记录、配置与授权缺失时不会调用；试听与接受使用下方单独控件。</p>
      <label className="experimental-check"><input type="checkbox" checked={skip} disabled={action.busy || !!selectedPreset} onChange={e => setSkip(e.target.checked)} />跳过同一来源与参数下已完成的校对、导出和已满意媒体结果</label>
      <Button disabled={action.busy || !available || !itemCount || itemCount > 20 || voiceIds.length !== selectedVoices.length || (!!voiceIds.length && !selectedAudioBroker) || chapters.some(id => !catalog.data!.chapters.some(c => c.id === id))} onClick={() => void action.run(async current => {
        const items: BatchInput[] = [];
        if (proof) chapters.forEach(id => items.push({ kind: 'PROOF', chapter_ids: [id], ...(chapters.length === 1 && (start || end) ? { start: Number(start || 0), end: end ? Number(end) : null } : {}) }));
        if (exporting && chapters.length) items.push({ kind: 'EXPORT', chapter_ids: chapters, format });
        if (selectedBrief) items.push({ kind: selectedBroker ? 'REGISTERED_MEDIA' : 'SYNTHETIC_MEDIA', brief_id: selectedBrief.id, expected_brief_version: selectedBrief.version, adapter_id: selectedBroker?.adapter_id || 'mock-image-v1', ...(selectedBroker ? { broker_preview_id: selectedBroker.id, expected_broker_version: selectedBroker.version } : {}) });
        if (selectedAudioBroker) selectedVoices.forEach(j => items.push({ kind: 'VOICE_REDO', voice_job_id: j.id, expected_voice_digest: j.request_digest, broker_preview_id: selectedAudioBroker.id, expected_broker_version: selectedAudioBroker.version }));
        await api.preflight(items, skip, selectedPreset); if (current()) reload();
      }, '已保存只读执行预检。请核对当前来源、权限与零费用预算后确认。')}>仅预检所选批次</Button>
    </Panel>
    <Panel title="批次快照与阶段结果">
      <ResourceState loading={records.loading} error={records.error} empty={recordsAvailable && !records.data!.items.length} />
      {recordsAvailable && records.data!.items.map(row => <article className="experimental-record" key={row.id} aria-label={`批次 ${row.id}`}>
        <div className="experimental-actions"><strong>批次 {row.id}</strong><Badge>{row.status} · v{row.version}</Badge></div>
        {row.stale ? <><StatusMessage tone="warning">来源、规则或预算配置已变化。旧内容已隐藏；请按当前选择重新预检。</StatusMessage><Details value={{ approvals: row.approvals, attempts: row.retained_receipts }} label="查看保留的原审批与成本回执" /></> : <>
          {!!row.approvals?.length && <Details value={row.approvals} label="查看原审批与后续重试审批记录" />}
          {row.preset && <p>参数模板：{row.preset.package_id} · 本项目副本 v{row.preset.version}</p>}
          <p>快照摘要：{row.snapshot_digest}；已知费用 0 USD；执行并发上限 1。</p>
          {row.items?.map(item => <div key={item.index} className="experimental-record"><div className="experimental-actions"><strong>阶段 {item.index + 1} · {item.kind}</strong><Badge>{item.status} · {item.attempts} 次尝试</Badge></div>
            <p>输入章节：{item.chapter_ids.join('、') || '已校验媒体简报'}；所需权限：{item.permission}</p>
            <Details value={{ versions: item.source_versions, parameters: item.configuration_summary, resources: item.resource_requirements, cost_state: item.cost_state }} label="核对来源版本与本阶段参数" />
            {!!item.receipts?.length && <Details value={item.receipts} label="查看历次尝试、原任务与成本回执" />}
            {!!item.satisfied_asset_ids?.length && <p>已跳过满意结果，保留正式资产：{item.satisfied_asset_ids.join('、')}</p>}
            {item.error_code && <StatusMessage tone="warning">{item.error_code}。先核对原任务与当前权限；结果未知时不会重放。</StatusMessage>}
            {item.findings && <Details value={item.findings} label="查看真实校对发现" />}
            {item.download_available && <Button disabled={action.busy} onClick={() => void action.run(async current => { const blob = await api.download(row, item.index); if (current()) downloadPortableBlob(blob, `batch-export.${item.format === 'markdown' ? 'md' : item.format}`); })}>下载阶段 {item.index + 1} 导出文件</Button>}
            {item.voice_result && <div><p>语音候选：{item.voice_result.duration_ms} 毫秒 · {item.voice_result.approval_status} · {item.voice_result.verification}</p>
              <Button disabled={action.busy} onClick={() => void action.run(async current => { const blob = await api.voicePreview(row, item.index); if (current()) setPreview({ id: `${row.id}:${item.index}`, url: URL.createObjectURL(blob), audio: true }); })}>试听阶段 {item.index + 1} 语音</Button>
              {preview?.id === `${row.id}:${item.index}` && preview.audio && <audio controls src={preview.url} aria-label={`阶段 ${item.index + 1} 语音试听`} />}
              {item.voice_result.approval_status !== 'APPROVED' && row.status !== 'UNKNOWN' && row.status !== 'CANCELLED' && <><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={!!proposalReviewed[`${row.id}:${item.index}`]} onChange={e => setProposalReviewed(v => ({ ...v, [`${row.id}:${item.index}`]: e.target.checked }))} />已试听并确认此语音段</label><Button disabled={action.busy || preview?.id !== `${row.id}:${item.index}` || !proposalReviewed[`${row.id}:${item.index}`]} onClick={() => void action.run(async current => { await api.approveVoice(row, item.index, item.voice_result!.asset_version); if (current()) reload(); }, '已通过原资产审核保留此语音段；没有重新生成。')}>确认接受此语音段</Button></>}
            </div>}
            {item.proposals?.map(p => <div key={p.id}><p>媒体候选：{p.verification} · {p.status} · {p.media.width} × {p.media.height}</p>
              <Button disabled={action.busy} onClick={() => void action.run(async current => { const blob = await api.preview(row, p); if (current()) setPreview({ id: p.id, url: URL.createObjectURL(blob) }); })}>预览媒体候选</Button>
              {preview?.id === p.id && <img src={preview.url} alt="实际解码的媒体候选" />}
              {p.status !== 'APPROVED' && row.status !== 'UNKNOWN' && <><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={!!proposalReviewed[p.id]} onChange={e => setProposalReviewed(v => ({ ...v, [p.id]: e.target.checked }))} />已预览并确认将此媒体候选登记为正式资产</label>
                <Button disabled={action.busy || !proposalReviewed[p.id] || preview?.id !== p.id || row.status === 'CANCELLED'} onClick={() => void action.run(async current => { await api.approve(row, p); if (current()) reload(); }, '已通过原媒体审核服务登记本候选，未重复接受其他结果。')}>确认接受此媒体候选</Button></>}
            </div>)}
          </div>)}
          {row.status === 'PREFLIGHT' && <><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={!!reviewed[row.id]} onChange={e => setReviewed(v => ({ ...v, [row.id]: e.target.checked }))} />已核对本批次来源版本、权限、资源与 0 USD 预算</label>
            <Button disabled={action.busy || !reviewed[row.id]} onClick={() => void action.run(async current => { await api.confirm(row); if (current()) reload(); }, '当前快照已确认，尚未执行。请点击执行下一阶段。')}>确认此批次快照与预算</Button></>}
          {['READY', 'PARTIAL'].includes(row.status) && row.items?.some(i => i.status === 'PENDING') && <Button disabled={action.busy} onClick={() => execute(row)}>执行下一阶段</Button>}
          {row.status === 'PARTIAL' && row.items?.some(i => i.status === 'FAILED') && <Button disabled={action.busy} onClick={() => void action.run(async current => { await api.retry(row); if (current()) reload(); }, '仅失败项已返回预检。已完成结果保留，重试前需要重新确认。')}>仅预检失败项重试</Button>}
          {row.status === 'UNKNOWN' && <><StatusMessage tone="warning">原执行结果未知。请先核对原任务和成本记录；本入口不自动重放，也不会把未知结果当作未收费。</StatusMessage><Button disabled={action.busy} onClick={() => void action.run(async current => { await api.reconcile(row); if (current()) reload(); }, '已核对原执行器与账本的终态回执，没有重新生成或下载。')}>仅查询原任务终态回执</Button></>}
        </>}
        {!['COMPLETED', 'CANCELLED'].includes(row.status) && <Button disabled={stop.busy} onClick={() => void stop.run(async current => { const fresh = (await api.list()).items.find(b => b.id === row.id); if (!current() || !fresh) return; await api.stop(fresh); if (current()) records.reload(); }, '已停止批次后续阶段。正在返回的本地结果将被丢弃；已完成成果保留。')}>停止此批次后续阶段</Button>}
      </article>)}
    </Panel>
  </section>;
}
