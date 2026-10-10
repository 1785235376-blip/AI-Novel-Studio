import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { saveOtioFile } from './timelineExchangeClient';
import { comicLayoutsClient, comicPreset, comicIssueLabel, type ComicDocument, type ComicRecord, type ComicPreflight, type ComicPanel, type ComicRect } from './comicLayoutsClient';
import './comicLayouts.css';
let nextScope = 0;
export function ComicLayoutsPanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++nextScope, [client]);
  return <ComicLayoutsContent key={identity} client={client} />;
}
function ComicLayoutsContent({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => comicLayoutsClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]); const records = useResource(signal => api.records(signal), [api]);
  const action = useReviewAction(); const epoch = useRef(0);
  const [document, setDocument] = useState<ComicDocument>(); const [row, setRow] = useState<ComicRecord>();
  const [past, setPast] = useState<ComicDocument[]>([]); const [future, setFuture] = useState<ComicDocument[]>([]); const [dirty, setDirty] = useState(false);
  const [report, setReport] = useState<ComicPreflight>(); const [segments, setSegments] = useState<string[]>([]); const [loadedSegments, setLoadedSegments] = useState<number[]>([]); const [previewFailed, setPreviewFailed] = useState(false); const [width, setWidth] = useState(360); const [reviewed, setReviewed] = useState(false);
  const [assetId, setAssetId] = useState(''); const [assetUrl, setAssetUrl] = useState(''); const [assetLoaded, setAssetLoaded] = useState(false); const [assetReviewed, setAssetReviewed] = useState(false);
  const [restoreVersion, setRestoreVersion] = useState('');
  const available = !catalog.loading && !catalog.error && !!catalog.data; const rowsReady = !records.loading && !records.error && !!records.data;
  const source = available ? catalog.data!.screenplays.find(s => s.id === document?.screenplay_id) : undefined;
  const sourceChanged = !!document && (!source || source.edit_version !== document.expected_screenplay_version);
  const savedCurrent = !!row && rowsReady && records.data!.items.some(r => r.id === row.id && r.version === row.version && !r.stale);
  const savedStale = !!row && rowsReady && records.data!.items.some(r => r.id === row.id && r.stale);
  const asset = available ? catalog.data!.assets.find(a => a.id === assetId) : undefined;
  useEffect(() => () => { segments.forEach(URL.revokeObjectURL); }, [segments]);
  useEffect(() => () => { if (assetUrl) URL.revokeObjectURL(assetUrl); }, [assetUrl]);
  const invalidate = () => { epoch.current++; setReport(undefined); setSegments([]); setLoadedSegments([]); setPreviewFailed(false); setReviewed(false); };
  const edit = (next: ComicDocument) => { if (document) setPast(values => [...values.slice(-29), document]); setDocument(next); setFuture([]); setDirty(true); invalidate(); };
  const load = (next: ComicRecord) => { invalidate(); setRow(next); setDocument(next.document); setPast([]); setFuture([]); setDirty(false); setRestoreVersion(''); };
  const refresh = () => { invalidate(); setAssetUrl(''); setAssetLoaded(false); setAssetReviewed(false); catalog.reload(); records.reload(); };
  const patchPanel = (id: string, patch: Partial<ComicPanel>) => document && edit({ ...document, panels: document.panels.map(p => p.id === id ? { ...p, ...patch } : p) });
  const runPreview = () => void action.run(async isCurrent => {
    if (!row) return; const ticket = ++epoch.current; setReport(undefined); setSegments([]); setLoadedSegments([]); setPreviewFailed(false); setReviewed(false);
    const result = await api.preflight(row); if (!isCurrent() || ticket !== epoch.current) return; setReport(result);
    if (result.can_render) { const blobs = await Promise.all(result.segments.map(segment => api.segment(row, segment.index))); if (isCurrent() && ticket === epoch.current) setSegments(blobs.map(blob => URL.createObjectURL(blob))); }
  });
  return <section className="experimental-section" aria-label="漫画与 Webtoon 排版">
    <div className="experimental-actions"><h3>漫画与 Webtoon 排版</h3><Badge>草稿 · 本地栅格渲染</Badge><Button disabled={action.busy || catalog.loading || records.loading} onClick={refresh}>刷新漫画来源与记录</Button></div>
    <p>复用原剧本镜头、人物与资产库。生成图片和排版分开；缺图会阻止预览和导出，测试素材不代表最终美术。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />{!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    {available && (!catalog.data!.font.available || !catalog.data!.renderer.available) && <StatusMessage tone="warning">{!catalog.data!.renderer.available ? '漫画渲染组件未就绪。' : ''}{!catalog.data!.font.available ? '未找到已校验的 OFL 中文字体。带文字布局不能预览或导出；请由环境维护者准备项目的固定版本字体，不会使用缺字方框代替。' : ''}</StatusMessage>}
    {available && <Panel title="核对原图库中的用户图片">
      <Field label="待核对的原图片"><select disabled={action.busy} value={assetId} onChange={e => { epoch.current++; setAssetId(e.target.value); setAssetUrl(''); setAssetLoaded(false); setAssetReviewed(false); }}><option value="">选择图片</option>{catalog.data!.assets.map(a => <option key={a.id} value={a.id}>{a.filename} · v{a.version}{a.approved ? ' · 已批准' : ' · 待审'}</option>)}</select></Field>
      {asset && <><Button disabled={action.busy} onClick={() => void action.run(async isCurrent => { const ticket = epoch.current; const blob = await api.image(asset.id); if (isCurrent() && ticket === epoch.current) { setAssetUrl(URL.createObjectURL(blob)); setAssetLoaded(false); setAssetReviewed(false); } })}>查看原图片像素</Button>
        {assetUrl && <img className="comic-source-preview" src={assetUrl} alt={`待审原图片：${asset.filename}`} onLoad={() => setAssetLoaded(true)} onError={() => setAssetLoaded(false)} />}
        {!asset.approved && asset.manual_review_available && <><label className="experimental-check"><input type="checkbox" disabled={!assetLoaded || action.busy} checked={assetReviewed} onChange={e => setAssetReviewed(e.target.checked)} />已查看此用户图片，并确认可用于漫画排版</label><Button disabled={action.busy || !assetReviewed || !assetLoaded} onClick={() => void action.run(async isCurrent => { await api.approveImage(asset); if (isCurrent()) refresh(); }, '已记录原图库图片的人工批准。请重新选取当前素材版本。')}>批准此用户图片</Button></>}
        {!asset.approved && !asset.manual_review_available && <StatusMessage>此图片必须回原生成任务进行审核，不能在排版区绕过。</StatusMessage>}
      </>}
    </Panel>}
    <Panel title="布局草稿与手工编辑">
      <Field label="漫画来源剧本"><select disabled={!available || action.busy} value={document?.screenplay_id || ''} onChange={e => { const source = catalog.data?.screenplays.find(s => s.id === e.target.value); invalidate(); setRow(undefined); setDocument(source ? comicPreset(source, 'PAGE', catalog.data!.presets.PAGE) : undefined); setPast([]); setFuture([]); setDirty(true); }}><option value="">选择已有镜头的剧本</option>{available && catalog.data!.screenplays.map(s => <option key={s.id} value={s.id}>{s.title} · v{s.edit_version}</option>)}</select></Field>
      {available && !catalog.data!.screenplays.length && <EmptyState title="暂无镜头来源" detail="先在原剧本工作区建立剧本与镜头，再回来选择。" />}
      {document && available && !savedStale && <>
        {sourceChanged && <StatusMessage tone="warning">来源版本已变化。草稿输入仍保留，请重新选择当前来源再保存；旧画面已隐藏。</StatusMessage>}
        <fieldset className="experimental-form" disabled={action.busy}>
          <Field label="漫画布局名称"><input maxLength={240} value={document.title} onChange={e => edit({ ...document, title: e.target.value })} /></Field>
          <Field label="布局预设"><select value={document.preset} onChange={e => { if (source) edit(comicPreset(source, e.target.value as ComicDocument['preset'], catalog.data!.presets[e.target.value as ComicDocument['preset']])); }}><option value="PAGE">页漫（最多前四个镜头，重排草稿）</option><option value="WEBTOON">纵向 Webtoon（最多前六个镜头，重排草稿）</option></select></Field>
          <Field label="漫画字体"><select value={document.font_family} onChange={() => {}}><option value="NOTO_SANS_SC_OFL">Noto Sans SC · 已固定版本的 SIL OFL 1.1 字体</option></select></Field>
          <div className="experimental-grid">{(['width', 'height', 'safe_area', 'segment_height'] as const).map((key, i) => <Field key={key} label={['页面宽度', '页面高度', '页面安全区', '导出分段高度'][i]}><input type="number" step={1} min={key === 'safe_area' ? 0 : 320} max={key === 'width' ? 1600 : key === 'height' ? 12000 : key === 'safe_area' ? 128 : 2400} value={document[key]} onChange={e => edit({ ...document, [key]: Number(e.target.value) })} /></Field>)}</div>
          <div className="experimental-actions"><Button disabled={!past.length} onClick={() => { const next = past.at(-1)!; setPast(past.slice(0, -1)); setFuture([document, ...future]); setDocument(next); setDirty(true); invalidate(); }}>撤销本地排版</Button><Button disabled={!future.length} onClick={() => { setPast([...past, document]); setDocument(future[0]); setFuture(future.slice(1)); setDirty(true); invalidate(); }}>重做本地排版</Button></div>
          {document.panels.map((panel, index) => <article className="experimental-record" key={panel.id} aria-label={`漫画格框 ${index + 1}`}><h4>格框 {index + 1}</h4><div className="experimental-grid">
            <Field label={`格框 ${index + 1} 镜头`}><select value={panel.shot_id} onChange={e => patchPanel(panel.id, { shot_id: e.target.value })}>{source && source.shots.map(shot => <option key={shot.id} value={shot.id}>镜头 {shot.number} · 场景 {shot.scene_id}</option>)}</select></Field>
            <Field label={`格框 ${index + 1} 阅读顺序`}><input type="number" min={1} max={24} step={1} value={panel.order} onChange={e => patchPanel(panel.id, { order: Number(e.target.value) })} /></Field>
            <Field label={`格框 ${index + 1} 已批准图片`}><select value={panel.asset_id || ''} onChange={e => { const asset = catalog.data!.assets.find(a => a.id === e.target.value); patchPanel(panel.id, { asset_id: asset?.id || null, expected_asset_version: asset?.version || null }); }}><option value="">缺图，导出将阻止</option>{catalog.data!.assets.filter(a => a.approved).map(a => <option key={a.id} value={a.id}>{a.filename} · v{a.version}</option>)}</select></Field>
            <Field label={`格框 ${index + 1} 图片缩放`}><select value={panel.fit} onChange={e => patchPanel(panel.id, { fit: e.target.value as ComicPanel['fit'] })}><option value="CONTAIN">完整显示，允许留白</option><option value="COVER">居中裁切填满（需审核）</option></select></Field>
          </div><RectFields label={`格框 ${index + 1}`} value={panel} onChange={patch => patchPanel(panel.id, patch)} />
            <Field label={`格框 ${index + 1} 关联人物`}><select multiple value={panel.character_ids} onChange={e => patchPanel(panel.id, { character_ids: Array.from(e.target.selectedOptions, o => o.value), appearance_references: (panel.appearance_references || []).filter(ref => Array.from(e.target.selectedOptions, o => o.value).includes(ref.character_id)) })}>{catalog.data!.characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
            <p>场景引用：{source?.shots.find(shot => shot.id === panel.shot_id)?.scene_id || '未提供'}。镜头与场景版本沿用原剧本。</p>
            <Field label={`格框 ${index + 1} 图片简报`}><textarea rows={3} maxLength={8000} value={panel.image_brief || ''} onChange={e => patchPanel(panel.id, { image_brief: e.target.value })} /></Field>
            <p>图片简报只保存创作意图。人物外观引用须来自原图库中已批准的图片，并绑定当前版本；不会启动生成。</p>
            {panel.character_ids.map(characterId => {
              const reference = panel.appearance_references?.find(ref => ref.character_id === characterId);
              const character = catalog.data!.characters.find(c => c.id === characterId);
              return <div key={characterId} className="experimental-record">
                <Field label={`格框 ${index + 1} ${character?.name || characterId} 外观参考`}><select value={reference?.asset_id || ''} onChange={e => {
                  const asset = catalog.data!.assets.find(a => a.id === e.target.value);
                  const rest = (panel.appearance_references || []).filter(ref => ref.character_id !== characterId);
                  patchPanel(panel.id, { appearance_references: asset ? [...rest, { character_id: characterId, asset_id: asset.id, expected_asset_version: asset.version, note: reference?.note || '' }] : rest });
                }}><option value="">未指定外观参考</option>{catalog.data!.assets.filter(a => a.approved).map(a => <option key={a.id} value={a.id}>{a.filename} · v{a.version}</option>)}</select></Field>
                {reference && <Field label={`格框 ${index + 1} ${character?.name || characterId} 外观说明`}><textarea maxLength={2000} value={reference.note} onChange={e => patchPanel(panel.id, { appearance_references: panel.appearance_references!.map(ref => ref.character_id === characterId ? { ...ref, note: e.target.value } : ref) })} /></Field>}
              </div>;
            })}
            {panel.bubbles.map((bubble, bi) => <fieldset className="experimental-form" key={bubble.id}><legend>格框 {index + 1} 气泡 {bi + 1}</legend>
              <Field label={`格框 ${index + 1} 气泡 ${bi + 1} 文字`}><textarea maxLength={1000} value={bubble.text} onChange={e => patchPanel(panel.id, { bubbles: panel.bubbles.map(b => b.id === bubble.id ? { ...b, text: e.target.value } : b) })} /></Field>
              <Field label={`格框 ${index + 1} 气泡 ${bi + 1} 类型`}><select value={bubble.kind} onChange={e => patchPanel(panel.id, { bubbles: panel.bubbles.map(b => b.id === bubble.id ? { ...b, kind: e.target.value as 'DIALOGUE' | 'NARRATION' } : b) })}><option value="DIALOGUE">对白气泡</option><option value="NARRATION">旁白框</option></select></Field>
              <Field label={`格框 ${index + 1} 气泡 ${bi + 1} 人物`}><select value={bubble.character_id || ''} onChange={e => patchPanel(panel.id, { bubbles: panel.bubbles.map(b => b.id === bubble.id ? { ...b, character_id: e.target.value || null } : b) })}><option value="">未指定 / 旁白</option>{catalog.data!.characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
              <Field label={`格框 ${index + 1} 气泡 ${bi + 1} 字号`}><input type="number" min={14} max={96} step={1} value={bubble.font_size} onChange={e => patchPanel(panel.id, { bubbles: panel.bubbles.map(b => b.id === bubble.id ? { ...b, font_size: Number(e.target.value) } : b) })} /></Field>
              <RectFields label={`格框 ${index + 1} 气泡 ${bi + 1}`} value={bubble} onChange={patch => patchPanel(panel.id, { bubbles: panel.bubbles.map(b => b.id === bubble.id ? { ...b, ...patch } : b) })} />
              <Button onClick={() => patchPanel(panel.id, { bubbles: panel.bubbles.filter(b => b.id !== bubble.id) })}>移除格框 {index + 1} 气泡 {bi + 1}</Button>
            </fieldset>)}
            <div className="experimental-actions"><Button disabled={panel.bubbles.length >= 12} onClick={() => patchPanel(panel.id, { bubbles: [...panel.bubbles, { id: globalThis.crypto.randomUUID(), kind: 'DIALOGUE', text: '输入对白', character_id: null, font_size: 32, x: panel.x + 16, y: panel.y + 16, width: Math.max(48, panel.width - 32), height: Math.min(160, Math.max(48, panel.height - 32)) }] })}>添加格框 {index + 1} 气泡</Button><Button disabled={document.panels.length === 1} onClick={() => edit({ ...document, panels: document.panels.filter(p => p.id !== panel.id).map((p, i) => ({ ...p, order: i + 1 })) })}>移除格框 {index + 1}</Button></div>
          </article>)}
          <Button disabled={document.panels.length >= 24 || !source?.shots.length} onClick={() => source && edit({ ...document, panels: [...document.panels, { id: globalThis.crypto.randomUUID(), shot_id: source.shots[0].id, order: document.panels.length + 1, x: document.safe_area, y: document.safe_area, width: document.width - document.safe_area * 2, height: 320, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', bubbles: [], image_brief: '', appearance_references: [] }] })}>添加格框（手工定位）</Button>
        </fieldset>
        <p>安全区与坐标以页面像素为准，阅读顺序支持从上到下、同一行从左到右。新增格框或气泡可能重叠，预检会阻止越界与文字溢出。切换预设会重排草稿，可撤销。</p>
        <Button disabled={action.busy || sourceChanged || !document.panels.length || !document.title.trim()} onClick={() => void action.run(async isCurrent => { const saved = await api.save(document, row); if (isCurrent()) { load(saved); records.reload(); } }, '布局已保存为待审草稿。原剧本与图片未改写。')}>保存漫画布局草稿</Button>
      </>}
    </Panel>
    <Panel title="已保存布局与版本"><ResourceState loading={records.loading} error={records.error} />{rowsReady && !records.data!.items.length && <EmptyState title="还没有漫画布局" detail="选择来源并保存草稿后，核对预检和实际像素，再显式批准导出。" />}
      {rowsReady && records.data!.items.map(record => <article className="experimental-record" key={record.id}><strong>{record.document?.title || '来源不可用的历史布局'}</strong> <Badge>{record.status} · v{record.version}</Badge>{record.stale ? <StatusMessage tone="warning">来源、授权或图片已变化，旧布局内容和导出已隐藏。</StatusMessage> : <Button disabled={action.busy} onClick={() => load(record)}>打开布局 {record.document?.title}</Button>}</article>)}
      {row && savedCurrent && <><Field label="恢复布局历史版本"><select disabled={action.busy} value={restoreVersion} onChange={e => setRestoreVersion(e.target.value)}><option value="">选择要恢复的版本</option>{row.history_versions?.map(v => <option key={v} value={v}>v{v}</option>)}</select></Field><Button disabled={action.busy || !restoreVersion} onClick={() => void action.run(async isCurrent => { const restored = await api.restore(row, Number(restoreVersion)); if (isCurrent()) { load(restored); records.reload(); } }, '已新增恢复后的草稿版本，必须重新审核。')}>恢复为新的布局草稿</Button></>}
    </Panel>
    {document && row && available && savedCurrent && !sourceChanged && <Panel title="真实分段预览与审核导出">
      {dirty && <StatusMessage tone="warning">存在未保存调整。请先保存草稿，再读取当前版本的预检。</StatusMessage>}
      <Button disabled={action.busy || dirty} onClick={runPreview}>预检并渲染当前布局</Button>
      {report && !dirty && <><p>当前审核版本 v{report.version}。预览使用与导出相同的 PNG 字节，屏宽只改变显示比例。</p>{report.issues.length ? <ul>{report.issues.map((issue, i) => <li key={i}><Badge tone={issue.severity === 'BLOCKER' ? 'error' : 'warning'}>{issue.severity}</Badge> {comicIssueLabel[issue.code] || issue.code} · {issue.target}</li>)}</ul> : <StatusMessage>预检未发现支持范围内的阻塞。</StatusMessage>}
        <Field label="漫画预览屏宽"><select value={width} onChange={e => setWidth(Number(e.target.value))}>{[320, 360, 768, 800].map(v => <option key={v} value={v}>{v} px</option>)}</select></Field>
        <div className="comic-preview-viewport"><div className="comic-preview" style={{ width }} aria-label="实际漫画分段像素">{segments.map((url, i) => <img key={url} src={url} alt={`漫画分段 ${i + 1}，${row.status === 'APPROVED' ? '已批准布局' : '待审草稿'}`} width={report.segments[i].width} height={report.segments[i].height} onLoad={() => setLoadedSegments(loaded => loaded.includes(i) ? loaded : [...loaded, i])} onError={() => { setPreviewFailed(true); setReviewed(false); }} />)}</div></div>
        {previewFailed && <StatusMessage tone="error">分段图片显示失败，请重新预检；未显示的画面不能批准。</StatusMessage>}
        {row.status !== 'APPROVED' && <><label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy || !report.can_render || !segments.length || previewFailed || loadedSegments.length !== segments.length} onChange={e => setReviewed(e.target.checked)} />已核对图片、阅读顺序、所有裁切与分段警告，并批准此布局版本</label><Button disabled={action.busy || !reviewed || !report.can_render || !segments.length || previewFailed || loadedSegments.length !== segments.length} onClick={() => void action.run(async isCurrent => { const approved = await api.approve(row, report); if (isCurrent()) { load(approved); records.reload(); } }, '此布局版本已显式批准。请重新渲染已批准版本后下载；不会自动发布。')}>批准当前漫画布局</Button></>}
        <Button disabled={action.busy || row.status !== 'APPROVED' || !report.can_render || !segments.length || previewFailed || loadedSegments.length !== segments.length} onClick={() => void action.run(async isCurrent => { const ticket = epoch.current; const blob = await api.download(row); if (isCurrent() && ticket === epoch.current) saveOtioFile(blob, 'comic-segments.zip'); }, '已生成分段 PNG、校验清单与适用字体许可的 ZIP 副本。没有发布或自动回写资产。')}>下载已批准漫画分段</Button>
      </>}
    </Panel>}
  </section>;
}
function RectFields({ label, value, onChange }: { label: string; value: ComicRect; onChange: (patch: Partial<ComicRect>) => void }) {
  return <div className="experimental-grid">{(['x', 'y', 'width', 'height'] as const).map((key, index) => <Field key={key} label={`${label} ${['横坐标', '纵坐标', '宽度', '高度'][index]}`}><input type="number" min={key === 'x' || key === 'y' ? 0 : 16} max={key === 'width' ? 1600 : 12000} step={1} value={value[key]} onChange={e => onChange({ [key]: Number(e.target.value) })} /></Field>)}</div>;
}
