import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { ErrorMessage, Field } from './shared';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import type { ComicBook, ComicBookDocument, ComicRecord } from './comicLayoutsClient';
import { comicAuthorArchiveClient, readAuthorArchive, readAuthorAttempt, withAuthorAttempt, type AuthorBytes, type AuthorInspection, type AuthorPreview, type AuthorRestore } from './comicAuthorArchiveClient';
import { saveOtioFile } from './timelineExchangeClient';
type Props = { client: ExperimentalClient; book?: ComicBook & ComicBookDocument; records: ComicRecord[]; disabled: boolean; collectionRevision: number; getCollectionRevision: () => number; isOwnerCurrent: () => boolean; getOwnerRevision: () => number; onBusyChange: (busy: boolean) => void; onRestored: (result: AuthorRestore) => void };
export function ComicAuthorArchivePanel(props: Props) {
  const api = useMemo(() => comicAuthorArchiveClient(props.client), [props.client]);
  const [preview, setPreview] = useState<AuthorPreview>(), [inspection, setInspection] = useState<AuthorInspection>();
  const [file, setFile] = useState<File>(), [exportAck, setExportAck] = useState(false), [restoreAck, setRestoreAck] = useState(false);
  const [recovering, setRecovering] = useState(false), [completedAttempt, setCompletedAttempt] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>();
  const live = useRef(props); live.current = props;
  const alive = useRef(true), pending = useRef(false), epoch = useRef(0), bytes = useRef<AuthorBytes>(), key = useRef(''), forceNew = useRef<string>();
  const reviewEpoch = useRef(-1), reviewOwner = useRef(-1), serial = useRef(0);
  const deps = [props.client, props.book, props.records, props.disabled, props.collectionRevision]; const scope = useRef(deps);
  if (deps.some((v, i) => v !== scope.current[i])) { scope.current = deps; epoch.current++; }
  const render = ++serial.current, renderedEpoch = epoch.current, owner = props.getOwnerRevision();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; if (pending.current) { pending.current = false; live.current.onBusyChange(false); } }; }, []);
  const current = () => alive.current && render === serial.current && renderedEpoch === epoch.current && live.current.isOwnerCurrent() && owner === live.current.getOwnerRevision() && props.collectionRevision === live.current.getCollectionRevision();
  const admitted = () => current() && !live.current.disabled && !pending.current;
  const reviewed = reviewEpoch.current === epoch.current && reviewOwner.current === owner && !props.disabled && props.isOwnerCurrent();
  const clear = () => { setPreview(undefined); setInspection(undefined); setExportAck(false); setRestoreAck(false); bytes.current = undefined; key.current = ''; forceNew.current = undefined; };
  const run = async <T,>(work: (valid: () => boolean) => Promise<T>, done: (value: T) => void) => {
    if (!admitted()) return;
    pending.current = true; setBusy(true); setError(undefined); live.current.onBusyChange(true);
    const ticket = epoch.current, revision = live.current.getOwnerRevision(), collection = live.current.getCollectionRevision();
    const valid = () => alive.current && epoch.current === ticket && live.current.isOwnerCurrent() && !live.current.disabled && revision === live.current.getOwnerRevision() && collection === live.current.getCollectionRevision();
    const release = () => { if (pending.current) { pending.current = false; if (alive.current) setBusy(false); live.current.onBusyChange(false); } };
    try { const result = await work(valid); if (valid()) { release(); reviewEpoch.current = epoch.current; reviewOwner.current = live.current.getOwnerRevision(); done(result); } }
    catch (reason) { if (valid()) { release(); reviewOwner.current = live.current.getOwnerRevision(); setError(reason); } }
    finally { release(); }
  };
  return <section aria-label="可编辑漫画作者归档">
    <h3>可编辑作者归档 · 私密内容</h3>
    <p>作者 ZIP 包含可编辑文字、隐藏图层文字和图片简述，不能作为公开阅读副本。仅支持无素材、无人物引用的独立 PAGE 页面，最多 10 页、2,000,000 字节；剧本、镜头、图片素材和 RASTER 图层会被拒绝，不会静默丢弃。</p>
    <p>恢复会创建新的未批准草稿，保留原书；不传递审批、历史或来源身份。需要已激活的原生独立项目；首次使用请先从项目列表创建或打开独立项目，再检查归档。</p>
    {!!error && (error instanceof ApiError ? <ErrorMessage error={error} /> : <StatusMessage tone="error">{error instanceof Error ? error.message : '读取或操作失败，请重试。'}</StatusMessage>)}{busy && <StatusMessage>正在检查或处理作者归档…</StatusMessage>}
    <Button disabled={props.disabled || busy || !props.book || !props.client.postBlob} onClick={() => { if (!props.book) return; void run(() => api.preview(props.book!, props.records), result => { clear(); setPreview(result); }); }}>检查当前书作者归档</Button>
    {reviewed && preview && <><p>已检查 {preview.page_count} 页 · 书结构 v{preview.book_version}。包含隐藏作者内容，不含批准状态。</p>
      <label className="experimental-check"><input type="checkbox" disabled={busy} checked={exportAck} onChange={e => { if (admitted()) setExportAck(e.target.checked); }} />我确认导出包含隐藏文字和图片简述的私密作者内容</label>
      <Button disabled={busy || !exportAck} onClick={() => { if (!exportAck || !reviewed || !props.book) return; void run(() => api.download(props.book!, preview), blob => { saveOtioFile(blob, 'comic-author.zip'); clear(); }); }}>下载可编辑作者归档</Button></>}
    <Field label="选择漫画作者 ZIP"><input type="file" accept=".zip,application/zip" disabled={props.disabled || busy} onChange={event => { if (!admitted()) return; epoch.current++; clear(); setError(undefined); setFile(event.target.files?.[0]); event.target.value = ''; }} /></Field>
    {file && <p>{file.name} · {file.size} 字节</p>}
    <Button disabled={props.disabled || busy || !file} onClick={() => { if (!file) return; clear(); void run(async valid => { const content = await readAuthorArchive(file); if (!valid()) throw new Error('作者归档范围已变化，请重新检查。'); const report = await api.inspect(content); return { content, report, prior: readAuthorAttempt(report.inspection_digest) }; }, ({ content, report, prior }) => { const completed = report.completed_attempts?.at(-1); bytes.current = content; key.current = prior?.request_key || completed?.request_key || crypto.randomUUID().replaceAll('-', ''); setRecovering(!!prior || !!completed); setCompletedAttempt(prior ? prior.status === 'COMPLETED' || report.completed_attempts.some(a => a.request_key === prior.request_key) : !!completed); setInspection(report); }); }}>只读检查作者归档</Button>
    {reviewed && inspection && <><p>待恢复：{inspection.title} · {inspection.page_count} 页 · 剩余恢复记录 {inspection.receipt_remaining}/{inspection.receipt_capacity}。检查未创建书或页面。</p>
      <label className="experimental-check"><input type="checkbox" disabled={busy} checked={restoreAck} onChange={e => { if (admitted()) setRestoreAck(e.target.checked); }} />确认恢复为新的未批准草稿，并保留原书</label>
      <Button disabled={busy || !restoreAck || (inspection.receipt_remaining === 0 && !recovering)} onClick={() => { if (!reviewed || !restoreAck || !bytes.current || !key.current) return; void run(valid => withAuthorAttempt(inspection.inspection_digest, key.current, forceNew.current, valid, async requestKey => { key.current = requestKey; forceNew.current = undefined; setRecovering(true); setCompletedAttempt(false); return api.restore(bytes.current!, inspection, requestKey); }), result => { clear(); setFile(undefined); live.current.onRestored(result); }); }}>恢复作者归档为新草稿</Button>
      {recovering && <><StatusMessage>已找到已有恢复标识。恢复按钮会核对并打开该次导入的当前结果，不重复创建；结果若已改变或不可用，服务器会明确拒绝。结果未知时必须先核对或恢复已有尝试，不能开始另一份导入。</StatusMessage>
        <Button disabled={busy || !completedAttempt || inspection.receipt_remaining === 0} onClick={() => { if (!admitted() || !reviewed || !completedAttempt) return; forceNew.current = key.current; key.current = crypto.randomUUID().replaceAll('-', ''); setRecovering(false); setRestoreAck(false); }}>明确开始另一份独立导入（将新增书和页面）</Button></>}
      <p>若响应丢失，请重新选择相同文件并只读检查，再明确重试；已保存的恢复标识会沿用，不自动提交。文件内容不保存在浏览器中。</p></>}
  </section>;
}
