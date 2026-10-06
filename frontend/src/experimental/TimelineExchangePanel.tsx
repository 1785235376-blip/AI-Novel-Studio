import { useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import type { DirectorScreenplay } from './directorClient';
import { timelineExchangeClient, readOtioFile, saveOtioFile, type ExchangeRecord, type Rational } from './timelineExchangeClient';
let nextScope = 0;
const rationalText = (value: Rational) => value.denominator === 1 ? `${value.numerator} 秒` : `${value.numerator}/${value.denominator} 秒`;
const lossLabels: Record<string, string> = {
  NAME_TRUNCATED_TO_240_CHARACTERS: '过长名称已截短至 240 字符', MISSING_MEDIA: '缺少媒体引用', MEDIA_REFERENCE_ONLY_NOT_PACKAGED: '仅生成媒体引用，文件未打包', TRANSITION_MEDIA_HANDLES_NOT_VERIFIED: '转场所需素材余量未实际验证',
  TRANSITION_NOT_REPRESENTED_CUT_USED: '不支持此转场，交换副本改为直接切点', SPEED_EFFECT_NOT_REPRESENTED_TIMING_UNVERIFIED: '变速效果未保留，效果后的时长未验证',
  EFFECT_NOT_REPRESENTED: '效果未保留', MARKERS_NOT_REPRESENTED: '标记未保留', APPLICATION_METADATA_MIX_SUBTITLES_NOT_REPRESENTED: '应用元数据、混音或字幕设置未保留',
  SUBTITLE_OR_UNKNOWN_TRACK_NOT_REPRESENTED: '字幕或未知轨道未保留', NESTED_COMPOSITION_REPLACED_WITH_GAP: '嵌套合成以等时长间隙代替',
  MEDIA_REFERENCE_TYPE_NOT_REPRESENTED: '不支持的媒体引用，保留为缺失素材', ALTERNATE_MEDIA_REFERENCES_NOT_REPRESENTED: '备用媒体引用未保留', DISABLED_ITEM_REPLACED_WITH_GAP: '停用片段以间隙代替',
};
export function TimelineExchangePanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++nextScope, [client]);
  return <TimelineExchangeContent key={identity} client={client} />;
}
function TimelineExchangeContent({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => timelineExchangeClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]); const records = useResource(signal => api.records(signal), [api]);
  const action = useReviewAction(); const [selected, setSelected] = useState<DirectorScreenplay>();
  const [media, setMedia] = useState<Record<string, string>>({}); const [included, setIncluded] = useState<string[]>([]); const [rate, setRate] = useState('24/1');
  const [file, setFile] = useState<File>(); const [acknowledged, setAcknowledged] = useState<Record<string, boolean>>({});
  const [filenameError, setFilenameError] = useState(''); const epoch = useRef(0);
  const available = !catalog.loading && !catalog.error && !!catalog.data;
  const recordsAvailable = !records.loading && !records.error && !!records.data;
  const parserReady = available && catalog.data!.parser.available;
  const current = available && catalog.data!.screenplays.find(row => row.id === selected?.id);
  const changed = !!selected && (!current || current.edit_version !== selected.edit_version);
  const refresh = () => { epoch.current++; setAcknowledged({}); catalog.reload(); records.reload(); };
  return <section className="experimental-section" aria-label="OTIO 剪辑交换">
    <div className="experimental-actions"><h3>OTIO 剪辑交换</h3><Badge>有理数时间 · 外部引用</Badge><Button disabled={action.busy || catalog.loading || records.loading} onClick={refresh}>刷新交换来源与记录</Button></div>
    <p>支持明确子集的片段、轨道、切点、间隙和叠化。这里生成新交换副本，不渲染、不自动读取或打包媒体，也不改写外部工程。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对本机会话、分支权限及 OTIO 与资产血缘开关后刷新。已选文件和输入仍保留。</StatusMessage>}
    {available && !parserReady && <StatusMessage tone="warning">缺少已验证的 OpenTimelineIO 0.18.1 解析器。请由环境维护者安装项目的 otio 可选依赖后刷新；应用不会自行安装软件。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    <Panel title="导入并检查 OTIO 副本">
      <Field label="选择本地 OTIO 文件"><input type="file" accept=".otio,application/json" disabled={action.busy} onChange={e => { epoch.current++; const next = e.target.files?.[0]; setFile(next); setFilenameError(next && (!/\.otio$/i.test(next.name) || !next.size || next.size > 2 * 1024 * 1024) ? '请选择不超过 2 MiB 的非空 .otio 文件。' : ''); }} /></Field>
      {file && <p>已选择：{file.name} · {file.size} 字节</p>}{filenameError && <StatusMessage tone="error">{filenameError}</StatusMessage>}
      <Button disabled={action.busy || !parserReady || !file || !!filenameError} onClick={() => void action.run(async isCurrent => { const ticket = epoch.current; const chosen = file!; const text = await readOtioFile(chosen); if (!isCurrent() || ticket !== epoch.current) return; await api.importFile(chosen.name, text); if (isCurrent() && ticket === epoch.current) records.reload(); }, '已用官方解析器读取并往返验证交换副本。下载前请核对信息损失与媒体引用。')}>检查并保存 OTIO 交换副本</Button>
      <p>外部媒体地址仅作为文本引用保留，不会发起网络请求。含凭据、查询参数或不支持协议的引用会被拒绝。</p>
    </Panel>
    <Panel title="从现有镜头建立交换副本">
      <Field label="OTIO 来源剧本"><select disabled={!available || action.busy} value={selected?.id || ''} onChange={e => { epoch.current++; const row = catalog.data?.screenplays.find(value => value.id === e.target.value); setSelected(row); setIncluded(row?.shots.map(shot => shot.id) || []); setMedia({}); }}><option value="">请选择已规划镜头的剧本</option>{available && catalog.data!.screenplays.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.edit_version}</option>)}</select></Field>
      {available && !catalog.data!.screenplays.length && <EmptyState title="暂无可交换镜头" detail="先在原剧本区建立镜头；也可以导入自己的 OTIO 文件检查支持范围。" />}
      {selected && <><Field label="交换时间基准帧率"><select value={rate} disabled={action.busy} onChange={e => setRate(e.target.value)}><option value="24/1">24</option><option value="25/1">25</option><option value="24000/1001">24000/1001</option><option value="30000/1001">30000/1001</option><option value="60/1">60</option></select></Field>
        {changed && <StatusMessage tone="warning">剧本已变化或不可用。请重新选择当前版本；不会把旧镜头与新媒体混合导出。</StatusMessage>}
        {selected.shots.map(shot => <article className="experimental-record" key={shot.id}><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={included.includes(shot.id)} onChange={() => setIncluded(ids => ids.includes(shot.id) ? ids.filter(id => id !== shot.id) : [...ids, shot.id])} />交换镜头 {shot.number} · {shot.duration_seconds} 秒</label><Field label={`镜头 ${shot.number} 的外部媒体引用`}><select disabled={action.busy || !available || !included.includes(shot.id)} value={media[shot.id] || ''} onChange={e => setMedia(values => ({ ...values, [shot.id]: e.target.value }))}><option value="">缺少媒体（仍可交换剪辑信息）</option>{available && catalog.data!.assets.filter(asset => /^(video|image)\//.test(asset.media_type)).map(asset => <option key={asset.id} value={asset.id}>{asset.filename} · v{asset.version}</option>)}</select></Field></article>)}
        <p>保留所选镜头在原剧本中的顺序。导出的 media/ 相对引用需要你另行放置已获授权的素材，文件不会被自动复制。</p>
        <Button disabled={action.busy || !parserReady || changed || !included.length} onClick={() => void action.run(async isCurrent => { await api.fromScreenplay(selected, rate.split('/').map(Number) as [number, number], selected.shots.filter(shot => included.includes(shot.id)).map(shot => ({ shot_id: shot.id, ...(media[shot.id] ? { asset_id: media[shot.id] } : {}) }))); if (isCurrent()) records.reload(); }, '已保存当前镜头的交换快照，并用官方解析器验证实际文件。请核对损失报告后下载。')}>创建镜头 OTIO 交换副本</Button>
      </>}
    </Panel>
    <Panel title="检查记录、损失与下载">
      <ResourceState loading={records.loading} error={records.error} />
      {recordsAvailable && !records.data!.items.length && <EmptyState title="还没有 OTIO 交换记录" detail="导入文件或选择现有镜头后，会在此显示支持范围、缺失素材和可下载的新文件。" />}
      {recordsAvailable && records.data!.items.map(row => <ExchangeCard key={row.id} row={row} acknowledged={acknowledged[row.id] || false} onAcknowledge={value => setAcknowledged(values => ({ ...values, [row.id]: value }))} disabled={action.busy || !parserReady} onDownload={() => void action.run(async isCurrent => { const ticket = epoch.current; const blob = await api.download(row, acknowledged[row.id] || false); if (isCurrent() && ticket === epoch.current) saveOtioFile(blob, row.filename!); }, '已准备新的 .otio 下载文件。外部原工程未修改；目标剪辑软件仍未实测。')} />)}
    </Panel>
    <StatusMessage>Resolve / Premiere 打开验证：NOT_RUN。FCPXML、CMX EDL、原生工程、效果、变速、混音、字幕及嵌套编辑暂不受支持。</StatusMessage>
  </section>;
}
function ExchangeCard({ row, acknowledged, onAcknowledge, disabled, onDownload }: { row: ExchangeRecord; acknowledged: boolean; onAcknowledge: (value: boolean) => void; disabled: boolean; onDownload: () => void }) {
  return <article className="experimental-record" aria-label={`OTIO 交换记录 ${row.id}`}><div className="experimental-actions"><strong>{row.summary?.name || '历史交换记录'}</strong><Badge>{row.origin} · v{row.version}</Badge>{row.stale && <Badge tone="warning">来源已变化</Badge>}</div>
    {row.stale ? <StatusMessage tone="warning">此交换记录的来源或素材已变化。旧引用与时序已隐藏，请按当前来源新建交换副本。</StatusMessage> : <>
      {row.summary?.tracks.map((track, index) => <div key={index}><h4>{track.name || `轨道 ${index + 1}`} · {track.kind} · {rationalText(track.duration_seconds)}</h4><ol>{track.cuts.map((cut, i) => <li key={i}>{cut.name || cut.kind} · 起点 {rationalText(cut.start_seconds)} · 时长 {rationalText(cut.duration_seconds)}</li>)}</ol></div>)}
      <h4>信息损失与警告</h4>{row.loss_report?.length ? <ul>{row.loss_report.map((loss, index) => <li key={index}><Badge tone="warning">{loss.severity}</Badge> {lossLabels[loss.code] || loss.code} · {loss.path}</li>)}</ul> : <p>支持子集内未检测到信息损失。外部媒体未打开验证。</p>}
      <Details value={row.media} label="核对外部媒体引用与缺失状态" />
      <label className="experimental-check"><input type="checkbox" checked={acknowledged} disabled={disabled} onChange={e => onAcknowledge(e.target.checked)} />已核对本记录的损失、媒体引用和目标软件未验证边界</label>
      <Button disabled={disabled || !acknowledged} onClick={onDownload}>下载新的 OTIO 文件</Button>
    </>}
  </article>;
}
