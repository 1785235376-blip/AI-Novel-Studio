import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { comicLayoutsClient, invalidPublication, type ComicBook, type ComicBookDocument, type ComicPublicationPreflight, type ComicReadingDirection, type ComicRecord } from './comicLayoutsClient';
import { ErrorMessage, Field } from './shared';
import { saveOtioFile } from './timelineExchangeClient';

type Props = {
  client: ExperimentalClient;
  book: ComicBook & ComicBookDocument;
  records: ComicRecord[];
  disabled: boolean;
  collectionRevision: number;
  getCollectionRevision: () => number;
  isOwnerCurrent: () => boolean;
  getOwnerRevision: () => number;
  onBusyChange: (busy: boolean) => void;
};
type Review = { report: ComicPublicationPreflight; epoch: number; ownerRevision: number };
const lossLabels: Record<string, string> = {
  FLATTENED_RGB_PNG_PAGES: '页面合成为 RGB PNG 图片',
  NO_EDITABLE_LAYERS_OR_TEXT: '文字和图层不再可编辑',
  DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS: '阅读方向仅写入元数据，不重排页面或格框',
  NO_DPI_BLEED_OR_PRINT_CONFORMANCE: '不包含 DPI、出血或印刷合规保证',
  EXTERNAL_READER_VALIDATION_NOT_RUN: '尚未验证外部阅读器兼容性',
  SOURCE_IMAGE_RIGHTS_NOT_VERIFIED: '尚未核验原图片的出版授权',
};

/** A read-only publication copy beneath the existing book owner, never a second editor. */
export function ComicPublicationPanel(props: Props) {
  const api = useMemo(() => comicLayoutsClient(props.client), [props.client]);
  const [direction, setDirection] = useState<ComicReadingDirection | ''>('');
  const [review, setReview] = useState<Review>(), [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(), [notice, setNotice] = useState('');
  const live = useRef(props); live.current = props;
  const alive = useRef(true), epoch = useRef(0), pending = useRef<number>(), acknowledged = useRef(false), renderSerial = useRef(0);
  const dependencies = [props.client, props.book, props.records, props.disabled, props.collectionRevision];
  const scope = useRef(dependencies);
  if (dependencies.some((value, index) => value !== scope.current[index])) { scope.current = dependencies; epoch.current++; acknowledged.current = false; }
  const thisRender = ++renderSerial.current, renderedEpoch = epoch.current, ownerRevision = props.getOwnerRevision();
  const release = (ticket: number) => {
    if (pending.current !== ticket) return;
    pending.current = undefined;
    if (alive.current) setBusy(false);
    live.current.onBusyChange(false);
  };
  useLayoutEffect(() => {
    alive.current = true;
    return () => { alive.current = false; epoch.current++; if (pending.current !== undefined) release(pending.current); };
  }, []);
  const current = () => alive.current && thisRender === renderSerial.current && renderedEpoch === epoch.current && live.current.isOwnerCurrent()
    && ownerRevision === live.current.getOwnerRevision() && props.collectionRevision === live.current.getCollectionRevision();
  const orderedPages = props.book.chapters.flatMap((chapter, chapterIndex) => chapter.pages.map((id, pageIndex) => ({
    id, chapterIndex, pageIndex, chapterTitle: chapter.title, page: props.records.find(row => row.id === id),
  })));
  const allApproved = orderedPages.length > 0 && orderedPages.length <= 100 && new Set(orderedPages.map(item => item.id)).size === orderedPages.length
    && orderedPages.every(({ page }) => page && !page.stale && page.status === 'APPROVED' && page.document?.source_mode === 'INDEPENDENT' && page.document.preset === 'PAGE');
  const admitted = () => current() && !live.current.disabled && pending.current === undefined && allApproved && !!props.client.postBlob;
  const clearReview = () => { setReview(undefined); setAck(false); acknowledged.current = false; };
  const reviewCurrent = !!review && review.epoch === epoch.current && review.ownerRevision === ownerRevision && !props.disabled && allApproved && props.isOwnerCurrent();

  const run = async <T,>(operation: () => Promise<T>, completed: (result: T, ticket: number) => void) => {
    if (!admitted()) return;
    const ticket = ++epoch.current; pending.current = ticket; setBusy(true); clearReview(); setError(undefined); setNotice('');
    live.current.onBusyChange(true);
    // The owning page editor intentionally advances its revision on busy changes.
    const actionOwner = live.current.getOwnerRevision(), collection = live.current.getCollectionRevision();
    const accepted = () => alive.current && ticket === epoch.current && live.current.isOwnerCurrent() && !live.current.disabled
      && actionOwner === live.current.getOwnerRevision() && collection === live.current.getCollectionRevision();
    try {
      const result = await operation();
      if (accepted()) {
        release(ticket);
        if (alive.current && ticket === epoch.current && live.current.isOwnerCurrent() && !live.current.disabled && collection === live.current.getCollectionRevision()) completed(result, ticket);
      }
    } catch (reason) { if (accepted()) { release(ticket); setError(reason); } }
    finally { release(ticket); }
  };
  const check = () => {
    if (!direction) return;
    void run(async () => {
      const report = await api.publicationPreflight(props.book, direction);
      if (!report || report.book_version !== props.book.version || report.reading_direction !== direction || report.page_count !== orderedPages.length
        || !Array.isArray(report.pages) || report.pages.length !== orderedPages.length || !/^[a-f0-9]{64}$/.test(report.publication_digest)
        || !Array.isArray(report.losses) || !report.losses.every(loss => typeof loss === 'string')
        || report.pages.some((page, index) => !page || page.id !== orderedPages[index].id || page.version !== orderedPages[index].page?.version || !/^[a-f0-9]{64}$/.test(page.review_digest))) return invalidPublication();
      return report;
    }, (report, ticket) => setReview({ report, epoch: ticket, ownerRevision: live.current.getOwnerRevision() }));
  };

  return <section aria-label="漫画书 CBZ 导出">
    <h3>出版副本 · CBZ</h3>
    <Badge>合成图片阅读副本</Badge>
    <p>按已保存的章节和页面顺序导出合成 PNG。文字和图层不再可编辑；不包含 DPI、出血或印刷合规保证，外部阅读器兼容性尚未验证。请自行核对原图片授权，导出不会授予出版权利。</p>
    <p>当前已保存书结构 v{props.book.version} · {orderedPages.length} 页。阅读方向仅写入元数据，不重排页面、不镜像格框，也不保证阅读器采用该方向。</p>
    <ol aria-label="CBZ 已保存页面顺序">{orderedPages.map(({ id, chapterIndex, pageIndex, chapterTitle, page }) => <li key={id}>
      {page && !page.stale && page.document ? `${chapterIndex + 1}.${pageIndex + 1} · ${chapterTitle} · ${page.document.title} · v${page.version}` : '页面不可用'}
    </li>)}</ol>
    {props.disabled && <StatusMessage tone="warning">请先保存或放弃书结构与页面修改，并等待其他操作结束，再检查出版副本。</StatusMessage>}
    {!allApproved && <StatusMessage tone="warning">CBZ 需要至少一页，且所有页面均为当前已批准的独立 PAGE 页面。请逐页完成预检与审核；WEBTOON 页面不能用于此导出。</StatusMessage>}
    {!props.client.postBlob && <StatusMessage tone="warning">当前入口不支持经过文件校验的 CBZ 下载。</StatusMessage>}
    <Field label="CBZ 阅读方向"><select value={direction} disabled={props.disabled || busy} onChange={event => {
      if (!current() || live.current.disabled || pending.current !== undefined || !['', 'LTR', 'RTL'].includes(event.target.value)) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); setDirection(event.target.value as ComicReadingDirection | '');
    }}><option value="">明确选择阅读方向</option><option value="LTR">从左到右（LTR）</option><option value="RTL">从右到左（RTL）</option></select></Field>
    <Button disabled={props.disabled || busy || !allApproved || !direction || !props.client.postBlob} onClick={check}>检查当前漫画书出版副本</Button>
    {busy && <StatusMessage>正在检查或生成 CBZ…放弃结果不会终止已发出的服务器处理。</StatusMessage>}
    {!!error && <ErrorMessage error={error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {reviewCurrent && <>
      <p>已检查 {review!.report.page_count} 页 · {review!.report.reading_direction} · 书结构 v{review!.report.book_version}</p>
      <ul aria-label="CBZ 导出限制">{review!.report.losses.map((loss, index) => <li key={index}>{lossLabels[loss] || loss}</li>)}</ul>
      <label className="experimental-check"><input type="checkbox" checked={ack && acknowledged.current} onChange={event => {
        if (!admitted() || !reviewCurrent) return;
        acknowledged.current = event.target.checked; setAck(event.target.checked);
      }} />已核对以上已保存页面顺序、阅读方向与合成图片限制</label>
      <Button disabled={busy || !ack || !acknowledged.current} onClick={() => {
        if (!reviewCurrent || !review || !acknowledged.current) return;
        void run(() => api.downloadCbz(props.book, review.report), blob => {
          saveOtioFile(blob, 'comic-book.cbz'); setNotice('已校验并下载 CBZ 合成图片副本。');
        });
      }}>下载已核对的 CBZ</Button>
    </>}
    {(busy || reviewCurrent) && <Button onClick={() => {
      if (!current()) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); if (pending.current !== undefined) release(pending.current);
    }}>放弃本次出版结果</Button>}
  </section>;
}
