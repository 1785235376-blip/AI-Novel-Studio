import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import type { ExperimentalClient } from './api';
import type { ComicRecord } from './comicLayoutsClient';
import { comicOraClient, oraThumbnail, readOraFile, type OraBytes, type OraManifest, type OraPreview, type OraReceipt } from './comicOraClient';

type Props = { client: ExperimentalClient; page?: ComicRecord; disabled: boolean; isOwnerCurrent: () => boolean; getOwnerRevision: () => number; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void; onAttached: (page: ComicRecord) => void };
export function ComicOraImportPanel({ client, page, disabled, isOwnerCurrent, getOwnerRevision, onBusyChange, onDirtyChange, onAttached }: Props) {
  const api = useMemo(() => comicOraClient(client), [client]);
  const [receipts, setReceipts] = useState<OraReceipt[]>([]), [receipt, setReceipt] = useState<OraReceipt>();
  const [file, setFile] = useState<File>(), [preview, setPreview] = useState<OraPreview>(), [manifest, setManifest] = useState<OraManifest>();
  const [thumbnail, setThumbnail] = useState(''), [pixels, setPixels] = useState<string[]>([]), [loaded, setLoaded] = useState<number[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [listed, setListed] = useState(false);
  const [ack, setAck] = useState(false), [license, setLicense] = useState(''), [pixelAck, setPixelAck] = useState(false);
  const alive = useRef(true), pending = useRef(false), epoch = useRef(0), bytes = useRef<OraBytes>(), urls = useRef<string[]>([]), requestKey = useRef('');
  const renderSerial = useRef(0); const thisRender = ++renderSerial.current;
  const renderEpoch = epoch.current, ownerRevision = getOwnerRevision();
  const current = () => alive.current && thisRender === renderSerial.current && isOwnerCurrent() && renderEpoch === epoch.current && ownerRevision === getOwnerRevision();
  const admitted = () => current() && !disabled && !pending.current;
  const clearPixels = () => { urls.current.forEach(url => URL.revokeObjectURL(url)); urls.current = []; setThumbnail(''); setPixels([]); setLoaded([]); setPixelAck(false); setManifest(undefined); setAck(false); };
  const clearFile = () => { onDirtyChange(false); bytes.current = undefined; requestKey.current = ''; setFile(undefined); setPreview(undefined); clearPixels(); setLicense(receipt?.review_license_note || ''); };
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; bytes.current = undefined; urls.current.forEach(url => URL.revokeObjectURL(url)); urls.current = []; }; }, []);
  const remember = (next: OraReceipt) => { setReceipt(next); if (next.review_license_note !== undefined) setLicense(next.review_license_note); setReceipts(items => [next, ...items.filter(item => item.id !== next.id)]); };
  const run = async (work: (valid: () => boolean) => Promise<void>) => {
    if (!admitted()) return;
    const ticket = ++epoch.current; pending.current = true; setBusy(true); setError(''); setNotice(''); onBusyChange(true);
    const revision = getOwnerRevision();
    const valid = () => alive.current && isOwnerCurrent() && ticket === epoch.current && revision === getOwnerRevision();
    try { await work(valid); } catch (reason) { if (valid()) setError(reason instanceof Error ? reason.message : 'ORA 操作未完成，请刷新记录并核对。'); }
    finally { pending.current = false; if (alive.current) { setBusy(false); onBusyChange(false); } }
  };
  const inputDirty = !!file || license !== (receipt?.review_license_note || '');
  const exactFile = !!bytes.current && !!receipt && bytes.current.archive_sha256 === receipt.archive_sha256;
  const staged = !!receipt && receipt.steps.length > 0 && receipt.steps.every(step => step.state !== 'PENDING');
  const pixelsReady = !!manifest && pixels.length === manifest.manifest.layers.length && pixels.length > 0 && loaded.length === pixels.length;
  const pageReady = !!page?.document && page.document.source_mode === 'INDEPENDENT' && !!manifest && page.document.width === manifest.manifest.page.width && page.document.height === manifest.manifest.page.height;
  return <Panel title="导入 OpenRaster（ORA）栅格图层">
    <Badge>外部栅格 · 来源未验证</Badge>
    <p>仅支持平面、普通混合的 ORA。文字与形状保持栅格像素，不恢复可编辑对白或生成来源。文件最多 16 MiB；文件字节只在本次打开期间保留，恢复时须重新选择完全相同的文件。</p>
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {busy && <StatusMessage>正在处理 ORA…</StatusMessage>}
    <Button disabled={disabled || busy} onClick={() => void run(async valid => { const result = await api.list(); if (valid()) { setReceipts(result.receipts); setListed(true); } })}>刷新可恢复的 ORA 导入</Button>
    {listed && !receipts.length && <p>暂无可恢复导入。</p>}
    <ul aria-label="可恢复的 ORA 导入">{receipts.map(item => <li key={item.id}><span>{item.id} · {item.status} · {item.steps.filter(step => step.state !== 'PENDING').length}/{item.steps.length} 层</span><Button disabled={disabled || busy || inputDirty} onClick={() => { if (inputDirty) return; void run(async valid => { clearFile(); const result = await api.status(item); if (valid()) remember(result); }); }}>恢复 {item.id}</Button></li>)}</ul>
    {receipt && <p className="experimental-details">当前导入 {receipt.id} · {receipt.status} · SHA-256 {receipt.archive_sha256}</p>}
    <Field label="选择 ORA 文件"><input type="file" accept=".ora,image/openraster" disabled={disabled || busy || inputDirty} onChange={event => { if (!admitted() || inputDirty) return; epoch.current++; clearFile(); setError(''); const selected = event.target.files?.[0]; onDirtyChange(!!selected); setFile(selected); event.target.value = ''; }} /></Field>
    {inputDirty && <StatusMessage>ORA 文件或授权说明尚在本地。切换导入或文件前，请明确清除选择；已暂存记录仍可恢复。</StatusMessage>}
    {file && <p>{file.name} · {file.size} 字节</p>}
    <Button disabled={disabled || busy || !file} onClick={() => void run(async valid => {
      if (!file) return; clearPixels(); bytes.current = undefined; setPreview(undefined);
      const content = await readOraFile(file); if (!valid()) return;
      if (receipt && content.archive_sha256 !== receipt.archive_sha256) throw new Error('文件与恢复记录的 SHA-256 不一致。请重新选择原文件，或明确开始新的导入。');
      const result = await api.preview(content); if (!valid()) return;
      if (result.report.archive_sha256 !== content.archive_sha256) throw new Error('预览摘要不一致，不能继续。');
      bytes.current = content; if (!requestKey.current) requestKey.current = globalThis.crypto.randomUUID(); setPreview(result);
      const url = URL.createObjectURL(oraThumbnail(result.thumbnail_base64)); urls.current.push(url); setThumbnail(url);
    })}>只读检查并预览 ORA</Button>
    <Button disabled={disabled || busy} onClick={() => { if (!admitted()) return; epoch.current++; clearFile(); setReceipt(undefined); setLicense(''); setError(''); setNotice(''); }}>清除选择 / 开始新的导入</Button>
    {preview && <><p>页面 {preview.report.width} × {preview.report.height} px · {preview.report.layers.length} 层。此预览尚未创建素材或附加到页面。</p><ul className="experimental-details">{preview.report.losses.map(loss => <li key={loss}>{loss}</li>)}</ul></>}
    {thumbnail && <img className="comic-source-preview" src={thumbnail} alt="ORA 只读合成缩略图（不能替代候选图层审核）" />}
    {!receipt && <Button disabled={disabled || busy || !preview || !bytes.current} onClick={() => void run(async valid => { if (!bytes.current || !preview || receipt) return; const result = await api.prepare(bytes.current, requestKey.current); if (valid()) remember(result); })}>确认准备 ORA 暂存记录</Button>}
    {receipt && <>
      <Button disabled={disabled || busy || !exactFile || staged || !!receipt.attachment} onClick={() => void run(async valid => { if (!bytes.current || !exactFile || staged || receipt.attachment) return; clearPixels(); const result = await api.stage(receipt, bytes.current); if (valid()) remember(result); })}>暂存 / 继续暂存下一批图层</Button>
      {!exactFile && <StatusMessage>恢复后先重新选择原 ORA 文件并完成只读检查。</StatusMessage>}
      <Button disabled={disabled || busy || !exactFile || !staged} onClick={() => void run(async valid => {
        if (!bytes.current || !exactFile || !staged) return; clearPixels(); const result = await api.manifest(receipt, bytes.current); if (!valid()) return;
        const next: string[] = [];
        try { for (let index = 0; index < result.manifest.layers.length; index++) { const blob = await api.candidate(receipt, index); if (!valid()) { next.forEach(url => URL.revokeObjectURL(url)); return; } next.push(URL.createObjectURL(blob)); } }
        catch (reason) { next.forEach(url => URL.revokeObjectURL(url)); throw reason; }
        urls.current.push(...next); setManifest(result); setPixels(next);
      })}>加载全部候选图层实际像素</Button>
      {manifest && <><p>候选页面 {manifest.manifest.page.width} × {manifest.manifest.page.height} px。以下逐层显示原始候选像素（包括隐藏图层），不是原生页面的排版预览。</p>
        {pixels.map((url, index) => <figure key={url}><img className="comic-source-preview" src={url} alt={`ORA 候选图层 ${index + 1}：${manifest.manifest.layers[index].name}`} onLoad={() => { if (current()) setLoaded(items => items.includes(index) ? items : [...items, index]); }} onError={() => { if (current()) { epoch.current++; setLoaded(items => items.filter(item => item !== index)); setPixelAck(false); setError('候选图层像素加载失败，请重新加载全部候选图层。'); } }} /><figcaption>{manifest.manifest.layers[index].name} · {manifest.manifest.layers[index].width} × {manifest.manifest.layers[index].height} px</figcaption></figure>)}
      </>}
      <label className="experimental-check"><input type="checkbox" disabled={disabled || busy || !pixelsReady} checked={pixelAck} onChange={event => { if (admitted()) { epoch.current++; setPixelAck(event.target.checked); } }} />已逐层查看全部候选实际像素</label>
      <Field label="ORA 素材授权说明"><input type="text" maxLength={1000} disabled={disabled || busy || receipt.review_license_note !== undefined} value={license} onChange={event => { if (admitted()) { epoch.current++; onDirtyChange(!!file || event.target.value !== (receipt.review_license_note || '')); setLicense(event.target.value); } }} /></Field>
      <label className="experimental-check"><input type="checkbox" disabled={disabled || busy} checked={ack} onChange={event => { if (admitted()) { epoch.current++; setAck(event.target.checked); } }} />确认有权使用这些素材，并接受文字栅格化、原生对白和来源证明无法恢复</label>
      <Button disabled={disabled || busy || !exactFile || !pixelsReady || !pixelAck || !ack || !license.trim() || receipt.status === 'REVIEWED_READY_FOR_ATTACHMENT' || !!receipt.attachment} onClick={() => void run(async valid => { if (!bytes.current || !manifest || !exactFile || !pixelsReady || !pixelAck || !ack || !license.trim() || receipt.status === 'REVIEWED_READY_FOR_ATTACHMENT' || receipt.attachment) return; const result = await api.review(receipt, bytes.current, manifest.manifest_digest, license); if (valid()) remember(result); })}>明确审核 / 继续审核下一批素材</Button>
      <p>附加目标必须为已保存、无未保存修改的独立漫画页，尺寸须与 ORA 一致。附加只创建待审页面版本，之后仍须正常预检、查看服务器像素和审核。</p>
      <Button disabled={disabled || busy || !pageReady || !pixelsReady || !pixelAck || !ack || receipt.status !== 'REVIEWED_READY_FOR_ATTACHMENT' || !receipt.review_digest || !!receipt.attachment} onClick={() => void run(async valid => { if (!page || !pageReady || !pixelsReady || !pixelAck || !ack || receipt.status !== 'REVIEWED_READY_FOR_ATTACHMENT' || !receipt.review_digest || receipt.attachment) return; const result = await api.attach(receipt, page); if (valid()) { remember(result.receipt); clearFile(); setLicense(result.receipt.review_license_note || ''); setNotice('图层已附加为待审草稿。请执行正常页面预检并核对服务器像素。'); onAttached(result.page); } })}>明确附加到当前已保存独立页</Button>
    </>}
  </Panel>;
}
