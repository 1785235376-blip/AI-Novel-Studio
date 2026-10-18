import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { comicLayoutsClient, invalidPublication, validComicPdfDpi, type ComicBook, type ComicBookDocument, type ComicPdfPublicationPreflight, type ComicPublicationPreflight, type ComicReadingDirection, type ComicRecord } from './comicLayoutsClient';
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
type PublicationFormat = 'CBZ' | 'PDF';
type CheckedPublication = { format: 'CBZ'; report: ComicPublicationPreflight } | { format: 'PDF'; report: ComicPdfPublicationPreflight };
type Review = CheckedPublication & { epoch: number; ownerRevision: number };
const pdfLosses = ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'CALLER_SELECTED_DPI_NOT_PRINT_QUALITY', 'NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'EXTERNAL_READER_VALIDATION_NOT_RUN'];
const lossLabels: Record<string, string> = {
  FLATTENED_RGB_PNG_PAGES: '页面合成为 RGB PNG 图片',
  FLATTENED_RGB_RASTER_PAGES: '页面合成为 RGB 栅格图片',
  NO_EDITABLE_LAYERS_OR_TEXT: '文字和图层不再可编辑',
  DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS: '阅读方向仅写入元数据，不重排页面或格框',
  NO_DPI_BLEED_OR_PRINT_CONFORMANCE: '不包含 DPI、出血或印刷合规保证',
  CALLER_SELECTED_DPI_NOT_PRINT_QUALITY: 'DPI 由你选择，仅确定页面尺寸，不代表印刷质量',
  NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE: '不包含出血，也不保证 PDF/A 或 PDF/X 合规',
  EXTERNAL_READER_VALIDATION_NOT_RUN: '尚未验证外部阅读器兼容性',
  SOURCE_IMAGE_RIGHTS_NOT_VERIFIED: '尚未核验原图片的出版授权',
};

/** A read-only publication copy beneath the existing book owner, never a second editor. */
export function ComicPublicationPanel(props: Props) {
  const api = useMemo(() => comicLayoutsClient(props.client), [props.client]);
  const [format, setFormat] = useState<PublicationFormat>('CBZ');
  const [dpi, setDpi] = useState('');
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
  const dpiValid = /^\d+$/.test(dpi) && validComicPdfDpi(Number(dpi));
  const reviewCurrent = !!review && review.format === format && (review.format !== 'PDF' || (dpiValid && review.report.dpi === Number(dpi)))
    && review.epoch === epoch.current && review.ownerRevision === ownerRevision && !props.disabled && allApproved && props.isOwnerCurrent();

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
    if (!direction || (format === 'PDF' && !dpiValid)) return;
    void run(async () => {
      const checked: CheckedPublication = format === 'PDF'
        ? { format, report: await api.pdfPublicationPreflight(props.book, direction, Number(dpi)) }
        : { format, report: await api.publicationPreflight(props.book, direction) };
      const report = checked.report;
      if (!report || report.book_version !== props.book.version || report.reading_direction !== direction || report.page_count !== orderedPages.length
        || !Array.isArray(report.pages) || report.pages.length !== orderedPages.length || !/^[a-f0-9]{64}$/.test(report.publication_digest)
        || !Array.isArray(report.losses) || !report.losses.every(loss => typeof loss === 'string')
        || report.pages.some((page, index) => !page || page.id !== orderedPages[index].id || page.version !== orderedPages[index].page?.version || !/^[a-f0-9]{64}$/.test(page.review_digest))) return invalidPublication();
      if (checked.format === 'PDF') {
        const pdf = checked.report;
        if (pdf.format !== 'comic-pdf-raster-v1' || pdf.dpi !== Number(dpi) || !pdfLosses.every(loss => pdf.losses.includes(loss))
          || !Array.isArray(pdf.page_dimensions) || pdf.page_dimensions.length !== orderedPages.length
          || pdf.page_dimensions.some((size, index) => {
            const document = orderedPages[index].page?.document;
            return !size || !document || !Number.isInteger(size.width_pixels) || !Number.isInteger(size.height_pixels)
              || size.width_pixels !== document.width || size.height_pixels !== document.height
              || !Number.isFinite(size.width_points) || !Number.isFinite(size.height_points) || size.width_points <= 0 || size.height_points <= 0
              || Math.abs(size.width_points - size.width_pixels * 72 / pdf.dpi) > 0.000001
              || Math.abs(size.height_points - size.height_pixels * 72 / pdf.dpi) > 0.000001;
          })) return invalidPublication();
      }
      return checked;
    }, (checked, ticket) => setReview({ ...checked, epoch: ticket, ownerRevision: live.current.getOwnerRevision() }));
  };

  return <section aria-label={`漫画书 ${format} 导出`}>
    <h3>出版副本 · {format}</h3>
    <Badge>合成图片阅读副本</Badge>
    <Field label="出版副本格式"><select value={format} disabled={props.disabled || busy} onChange={event => {
      if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === format || !['CBZ', 'PDF'].includes(event.target.value)) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); setFormat(event.target.value as PublicationFormat);
    }}><option value="CBZ">CBZ · 合成 PNG 图片</option><option value="PDF">PDF · 合成 RGB 栅格图片</option></select></Field>
    {format === 'CBZ'
      ? <p>按已保存的章节和页面顺序导出合成 PNG。文字和图层不再可编辑；不包含 DPI、出血或印刷合规保证，外部阅读器兼容性尚未验证。请自行核对原图片授权，导出不会授予出版权利。</p>
      : <><p>按已保存的章节和页面顺序导出合成 RGB 栅格 PDF。文字和图层不再可编辑；DPI 仅确定页面尺寸，不提高图片分辨率或保证印刷质量。不包含出血，也不保证 PDF/A 或 PDF/X 合规。外部阅读器兼容性尚未验证，请自行核对原图片授权。</p>
        <p>PDF 是有容量限制的阅读副本：每次请求总页面像素约 270 万以内，页面开销会进一步降低额度。高分辨率或多页漫画书可能被拒绝；降低 DPI 不会降低原页面像素用量。</p></>}
    <p>当前已保存书结构 v{props.book.version} · {orderedPages.length} 页。阅读方向仅写入元数据，不重排页面、不镜像格框，也不保证阅读器采用该方向。</p>
    <ol aria-label={`${format} 已保存页面顺序`}>{orderedPages.map(({ id, chapterIndex, pageIndex, chapterTitle, page }) => <li key={id}>
      {page && !page.stale && page.document ? `${chapterIndex + 1}.${pageIndex + 1} · ${chapterTitle} · ${page.document.title} · v${page.version}` : '页面不可用'}
    </li>)}</ol>
    {props.disabled && <StatusMessage tone="warning">请先保存或放弃书结构与页面修改，并等待其他操作结束，再检查出版副本。</StatusMessage>}
    {!allApproved && <StatusMessage tone="warning">{format} 需要至少一页，且所有页面均为当前已批准的独立 PAGE 页面。请逐页完成预检与审核；WEBTOON 页面不能用于此导出。</StatusMessage>}
    {!props.client.postBlob && <StatusMessage tone="warning">当前入口不支持经过文件校验的 {format} 下载。</StatusMessage>}
    <Field label={`${format} 阅读方向`}><select value={direction} disabled={props.disabled || busy} onChange={event => {
      if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === direction || !['', 'LTR', 'RTL'].includes(event.target.value)) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); setDirection(event.target.value as ComicReadingDirection | '');
    }}><option value="">明确选择阅读方向</option><option value="LTR">从左到右（LTR）</option><option value="RTL">从右到左（RTL）</option></select></Field>
    {format === 'PDF' && <>
      <Field label="PDF DPI（36–600 整数，需明确填写）"><input type="number" min={36} max={600} step={1} value={dpi} disabled={props.disabled || busy} onChange={event => {
        if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === dpi) return;
        epoch.current++; clearReview(); setError(undefined); setNotice(''); setDpi(event.target.value);
      }} /></Field>
      <p>请根据目标页面尺寸选择 DPI，没有默认印刷质量。PDF 页面尺寸（pt）= 像素尺寸 × 72 ÷ DPI。</p>
      {dpi !== '' && !dpiValid && <StatusMessage tone="warning">PDF DPI 必须是 36–600 的整数。</StatusMessage>}
    </>}
    <Button disabled={props.disabled || busy || !allApproved || !direction || (format === 'PDF' && !dpiValid) || !props.client.postBlob} onClick={check}>检查当前漫画书出版副本</Button>
    {busy && <StatusMessage>正在检查或生成 {format}…放弃结果不会终止已发出的服务器处理。</StatusMessage>}
    {!!error && <ErrorMessage error={error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {reviewCurrent && <>
      <p>已检查 {review!.report.page_count} 页 · {review!.report.reading_direction} · 书结构 v{review!.report.book_version}</p>
      {review!.format === 'PDF' && <>
        <p>已核对 PDF · {review!.report.dpi} DPI</p>
        <ol aria-label="PDF 已检查页面尺寸">{review!.report.page_dimensions.map((size, index) => <li key={index}>
          第 {index + 1} 页 · {size.width_pixels} × {size.height_pixels} px · {size.width_points.toFixed(3)} × {size.height_points.toFixed(3)} pt
        </li>)}</ol>
      </>}
      <ul aria-label={`${format} 导出限制`}>{review!.report.losses.map((loss, index) => <li key={index}>{lossLabels[loss] || loss}</li>)}</ul>
      <label className="experimental-check"><input type="checkbox" checked={ack && acknowledged.current} onChange={event => {
        if (!admitted() || !reviewCurrent) return;
        acknowledged.current = event.target.checked; setAck(event.target.checked);
      }} />{format === 'PDF' ? '已核对以上已保存页面顺序、阅读方向、DPI、页面尺寸与合成图片限制' : '已核对以上已保存页面顺序、阅读方向与合成图片限制'}</label>
      <Button disabled={busy || !ack || !acknowledged.current} onClick={() => {
        if (!reviewCurrent || !review || !acknowledged.current) return;
        void run(() => review.format === 'PDF' ? api.downloadPdf(props.book, review.report) : api.downloadCbz(props.book, review.report), blob => {
          saveOtioFile(blob, `comic-book.${review.format.toLowerCase()}`); setNotice(`已校验并下载 ${review.format} 合成图片副本。`);
        });
      }}>下载已核对的 {format}</Button>
    </>}
    {(busy || reviewCurrent) && <Button onClick={() => {
      if (!current()) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); if (pending.current !== undefined) release(pending.current);
    }}>放弃本次出版结果</Button>}
  </section>;
}
