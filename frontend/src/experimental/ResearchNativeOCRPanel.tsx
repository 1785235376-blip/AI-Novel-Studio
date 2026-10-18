import { useMemo, useRef, useState } from 'react';
import type { ExperimentalClient } from './api';
import type { Source } from './researchLibraryClient';
import { currentOCR, researchNativeOCRClient, type OCRRow } from './researchNativeOCRClient';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
let nextScope = 0;
export function ResearchNativeOCRPanel({ client, source }: { client: ExperimentalClient; source: Source }) {
  const scope = useMemo(() => ++nextScope, [client, source.id, source.version, source.content_sha256]);
  return <OCRControls key={scope} client={client} source={source} />;
}
function OCRControls({ client, source }: { client: ExperimentalClient; source: Source }) {
  const api = useMemo(() => researchNativeOCRClient(client), [client]);
  const catalog = useResource(signal => api.status(signal), [api]);
  const receipts = useResource(signal => api.list(signal), [api]);
  const action = useReviewAction();
  const [row, setRow] = useState<OCRRow>();
  const [routeIndex, setRouteIndex] = useState('0'), [language, setLanguage] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const attempt = useRef<{ digest: string; key: string }>();
  const routes = !catalog.loading && !catalog.error && catalog.data?.native_ocr?.status === 'CONFIGURED' ? catalog.data.native_ocr.routes : [];
  const route = routes[Number(routeIndex)];
  const lang = route?.languages.includes(language) ? language : route?.languages[0] || '';
  const preview = row?.status === 'DRAFT' ? row.native_ocr_preview : undefined;
  const validPreview = !!preview && preview.receipt_version === row?.version && preview.provider_id === route?.provider_id && preview.model_id === route?.model_id && preview.language === lang && preview.source_binding.source_id === source.id && preview.source_binding.source_version === source.version && preview.source_binding.source_digest === source.content_sha256 && Date.parse(preview.expires_at) > Date.now();
  const accept = (value: OCRRow) => { if (!currentOCR(value, source)) throw new Error('OCR 来源已变化'); setRow(value); setConfirmed(false); };
  const load = (id: string) => action.run(async alive => { setRow(undefined); setConfirmed(false); const value = await api.get(id); if (alive()) accept(value); });
  const makePreview = () => action.run(async alive => {
    if (!route || !lang) return;
    let value = row && ['DRAFT', 'NOT_CONFIGURED', 'FAILED'].includes(row.status) ? row : await api.create(source);
    if (!alive()) return;
    accept(value);
    value = await api.preview(value, route, lang);
    if (alive()) { accept(value); attempt.current = undefined; receipts.reload(); }
  });
  const dispatch = () => action.run(async alive => {
    if (!row || !validPreview || !confirmed) return;
    const digest = row.native_ocr_preview!.reviewed_preview_digest;
    if (attempt.current?.digest !== digest) attempt.current = { digest, key: globalThis.crypto?.randomUUID?.() || `ocr-${Date.now()}-${Math.random().toString(16).slice(2)}` };
    const value = await api.dispatch(row, attempt.current.key);
    if (alive()) { accept(value); receipts.reload(); }
  });
  return <Panel title="本地图片文字识别"><p>仅识别所选 PNG / JPEG 图片。结果单独保存，需人工审核，不改写原图、正文或 Canon。服务调用费为零，仍占用本机算力；不自动转云端。</p>
    <ResourceState loading={catalog.loading || receipts.loading} error={catalog.error || receipts.error} />
    {!catalog.loading && !catalog.error && !routes.length && <StatusMessage>本地 OCR 未配置或相关功能未启用。请管理员按已安装的可信程序和语言文件配置；这里不下载或安装软件。</StatusMessage>}
    {routes.length > 0 && <div className="experimental-form"><Field label="OCR 本地模型"><select value={routeIndex} disabled={action.busy} onChange={e => { setRouteIndex(e.target.value); setLanguage(''); setConfirmed(false); }}>{routes.map((item, index) => <option key={`${item.provider_id}:${item.model_id}`} value={index}>{item.display_name}</option>)}</select></Field><Field label="识别语言"><select value={lang} disabled={action.busy} onChange={e => { setLanguage(e.target.value); setConfirmed(false); }}>{route?.languages.map(value => <option key={value}>{value}</option>)}</select></Field><Button disabled={action.busy || !route || !lang || row?.status === 'RUNNING'} onClick={() => void makePreview()}>生成 OCR 执行预览</Button></div>}
    {preview && <section className="experimental-record" aria-label="OCR 执行预览"><p>来源 v{preview.source_binding.source_version} · {preview.provider_id} / {preview.model_id} · {preview.language}</p><p>预览有效期至 {preview.expires_at}。配置不等于识别质量保证。</p><label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={action.busy || !validPreview} onChange={e => setConfirmed(e.target.checked)} />已核对来源与本地模型，同意执行本次 OCR</label><Button disabled={action.busy || !validPreview || !confirmed} onClick={() => void dispatch()}>确认执行 OCR</Button></section>}
    {!!action.error && <ErrorMessage error={action.error} />}
    <Button disabled={action.busy} onClick={() => { catalog.reload(); receipts.reload(); if (row) void load(row.id); }}>刷新 OCR 状态</Button>
    {!receipts.loading && !receipts.error && receipts.data?.items.filter(item => currentOCR(item, source)).map(item => <Button key={item.id} disabled={action.busy} onClick={() => void load(item.id)}>打开 OCR 记录 {item.id}</Button>)}
    {row && !action.error && <section className="experimental-record" aria-label="OCR 当前结果"><Badge>{row.status} · v{row.version}</Badge>{row.recovery && <StatusMessage tone="warning">当前无法接续原执行器，不能自动恢复或重放。{row.recovery.budget_hold_retained ? '调度占用仍保留，需管理员明确核对执行器后处理；重新打开不会释放占用。' : '需要管理员核对原任务，不会自动重新识别。'}</StatusMessage>}<p>运行任务不会在重新打开时自动重做；可刷新读取已保存状态。</p>{row.result?.blocks.map((block, index) => <article key={index}><p>{block.text}</p><p>来源 {block.citation.source_id} · v{block.citation.source_version} · 第 {block.page} 页 · 摘要 {block.citation.result_digest}</p></article>)}{row.status === 'REVIEW_REQUIRED' && <Button disabled={action.busy} onClick={() => void action.run(async alive => { const value = await api.action(row, 'review'); if (alive()) { accept(value); receipts.reload(); } })}>核对文字后标记已审核</Button>}{row.status === 'REVIEWED' && <Button disabled={action.busy} onClick={() => void action.run(async alive => {
      const blob = await api.exportReviewed(row); if (!alive()) return;
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = 'research-ocr.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    })}>导出已审核文字 TXT</Button>}{['DRAFT', 'RUNNING', 'NOT_CONFIGURED'].includes(row.status) && <Button disabled={action.busy} onClick={() => void action.run(async alive => { const value = await api.action(row, 'cancel'); if (alive()) { accept(value); receipts.reload(); } })}>取消此 OCR 任务</Button>}</section>}
  </Panel>;
}
