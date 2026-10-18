import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { comicLayoutsClient, comicPageArchiveLimits, comicPublicationMaxOutputBytes, invalidPublication, validComicEpubOptions, validComicPageArchiveOptions, validComicPdfDpi, type ComicBook, type ComicBookDocument, type ComicEpubPublicationPreflight, type ComicPageArchivePreflight, type ComicPdfPublicationPreflight, type ComicPublicationPreflight, type ComicReadingDirection, type ComicRecord } from './comicLayoutsClient';
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
type PublicationFormat = 'CBZ' | 'PDF' | 'EPUB' | 'JPEG' | 'WEBP';
type CheckedPublication = { format: 'CBZ'; report: ComicPublicationPreflight } | { format: 'PDF'; report: ComicPdfPublicationPreflight } | { format: 'EPUB'; report: ComicEpubPublicationPreflight } | { format: 'JPEG' | 'WEBP'; report: ComicPageArchivePreflight };
type Review = CheckedPublication & { epoch: number; ownerRevision: number };
const epubLosses = ['FLATTENED_RGB_PNG_PAGES', 'NO_EDITABLE_OR_SEARCHABLE_TEXT', 'RASTER_ONLY_LIMITED_ACCESSIBILITY_NO_TEXT_ALTERNATIVE', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'NO_DPI_BLEED_COLOR_PROFILE_OR_PRINT_CONFORMANCE', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'LANGUAGE_UNSPECIFIED_UND', 'EPUBCHECK_NOT_RUN', 'EXTERNAL_READER_VALIDATION_NOT_RUN'];
const pdfLosses = ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'CALLER_SELECTED_DPI_NOT_PRINT_QUALITY', 'NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'EXTERNAL_READER_VALIDATION_NOT_RUN'];
const archiveLosses = ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'NO_COLOR_PROFILE_OR_PRINT_FIDELITY', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'EXTERNAL_READER_VALIDATION_NOT_RUN'];
const lossLabels: Record<string, string> = {
  NO_EDITABLE_OR_SEARCHABLE_TEXT: '文字仅存在于图片中，无法搜索或编辑',
  RASTER_ONLY_LIMITED_ACCESSIBILITY_NO_TEXT_ALTERNATIVE: '仅含栅格图片，无文字替代内容，无障碍支持有限',
  NO_DPI_BLEED_COLOR_PROFILE_OR_PRINT_CONFORMANCE: '不包含 DPI、出血、色彩配置文件或印刷合规保证',
  LANGUAGE_UNSPECIFIED_UND: '语言明确设为 Unspecified (und)，不推断内容语言',
  EPUBCHECK_NOT_RUN: '独立 EPUBCheck 验收：NOT_RUN',
  FLATTENED_RGB_PNG_PAGES: '页面合成为 RGB PNG 图片',
  FLATTENED_RGB_RASTER_PAGES: '页面合成为 RGB 栅格图片',
  NO_EDITABLE_LAYERS_OR_TEXT: '文字和图层不再可编辑',
  DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS: '阅读方向仅写入元数据，不重排页面或格框',
  NO_DPI_BLEED_OR_PRINT_CONFORMANCE: '不包含 DPI、出血或印刷合规保证',
  CALLER_SELECTED_DPI_NOT_PRINT_QUALITY: 'DPI 由你选择，仅确定页面尺寸，不代表印刷质量',
  NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE: '不包含出血，也不保证 PDF/A 或 PDF/X 合规',
  EXTERNAL_READER_VALIDATION_NOT_RUN: '尚未验证外部阅读器兼容性',
  SOURCE_IMAGE_RIGHTS_NOT_VERIFIED: '尚未核验原图片的出版授权',
  NO_COLOR_PROFILE_OR_PRINT_FIDELITY: '不保留原色彩配置文件，不保证印刷或色彩保真',
  PIXEL_EXACT_FLATTENED_RGB_ONLY: '无损仅保证与本次合成 RGB 页面像素完全一致',
  LOSSY_PIXELS_INCLUDING_QUALITY_100: '有损编码会改变像素，质量 100 仍然有损',
};

/** A read-only publication copy beneath the existing book owner, never a second editor. */
export function ComicPublicationPanel(props: Props) {
  const api = useMemo(() => comicLayoutsClient(props.client), [props.client]);
  const [format, setFormat] = useState<PublicationFormat>('CBZ');
  const [language, setLanguage] = useState<'' | 'und'>('');
  const [dpi, setDpi] = useState('');
  const [lossMode, setLossMode] = useState<'LOSSY' | 'LOSSLESS' | ''>('');
  const [quality, setQuality] = useState('');
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
  const isArchive = format === 'JPEG' || format === 'WEBP';
  const epubOptions = { format: 'comic-epub-fixed-raster-v1', language };
  const epubOptionsValid = validComicEpubOptions(epubOptions);
  const archiveOptions = { image_format: format, loss_mode: lossMode, quality: lossMode === 'LOSSLESS' ? null : quality === '' ? undefined : Number(quality) };
  const archiveOptionsValid = validComicPageArchiveOptions(archiveOptions);
  const totalPagePixels = orderedPages.reduce((sum, { page }) => sum + (page?.document ? page.document.width * page.document.height : 0), 0);
  const archiveWithinLimits = orderedPages.length <= comicPageArchiveLimits.max_pages && totalPagePixels <= comicPageArchiveLimits.max_total_page_pixels
    && orderedPages.every(({ page }) => page?.document && [page.document.width, page.document.height].every(side => Number.isInteger(side) && side > 0 && side <= comicPageArchiveLimits.max_side_pixels));
  const admitted = () => current() && !live.current.disabled && pending.current === undefined && allApproved && (!isArchive || archiveWithinLimits) && (format !== 'EPUB' || epubOptionsValid) && !!props.client.postBlob;
  const clearReview = () => { setReview(undefined); setAck(false); acknowledged.current = false; };
  const dpiValid = /^\d+$/.test(dpi) && validComicPdfDpi(Number(dpi));
  const reviewCurrent = !!review && review.format === format && (review.format !== 'EPUB' || (epubOptionsValid && review.report.language === language)) && (review.format !== 'PDF' || (dpiValid && review.report.dpi === Number(dpi)))
    && ((review.format !== 'JPEG' && review.format !== 'WEBP') || (archiveOptionsValid && archiveWithinLimits && review.report.image_format === archiveOptions.image_format && review.report.loss_mode === archiveOptions.loss_mode && review.report.quality === archiveOptions.quality))
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
    if (!direction || (format === 'EPUB' && !epubOptionsValid) || (format === 'PDF' && !dpiValid) || (isArchive && (!archiveOptionsValid || !archiveWithinLimits))) return;
    void run(async () => {
      const checked: CheckedPublication = (format === 'JPEG' || format === 'WEBP') && validComicPageArchiveOptions(archiveOptions)
        ? { format, report: await api.pageArchivePreflight(props.book, direction, archiveOptions) } : format === 'PDF'
        ? { format, report: await api.pdfPublicationPreflight(props.book, direction, Number(dpi)) }
        : format === 'EPUB' && validComicEpubOptions(epubOptions) ? { format, report: await api.epubPublicationPreflight(props.book, direction, epubOptions) }
        : { format: 'CBZ', report: await api.publicationPreflight(props.book, direction) };
      const report = checked.report;
      if (!report || report.book_version !== props.book.version || report.reading_direction !== direction || report.page_count !== orderedPages.length
        || !Array.isArray(report.pages) || report.pages.length !== orderedPages.length || !/^[a-f0-9]{64}$/.test(report.publication_digest)
        || !Array.isArray(report.losses) || !report.losses.every(loss => typeof loss === 'string')
        || report.pages.some((page, index) => !page || page.id !== orderedPages[index].id || page.version !== orderedPages[index].page?.version || !/^[a-f0-9]{64}$/.test(page.review_digest))) return invalidPublication();
      if (checked.format === 'EPUB') {
        const epub = checked.report, limits = epub.epub_limits;
        if (!validComicEpubOptions(epub) || epub.language !== language || !epubLosses.every(loss => epub.losses.includes(loss))
          || !Array.isArray(epub.page_dimensions) || epub.page_dimensions.length !== orderedPages.length
          || epub.page_dimensions.some((size, index) => {
            const document = orderedPages[index].page?.document;
            return !size || !document || !Number.isSafeInteger(size.width_pixels) || !Number.isSafeInteger(size.height_pixels)
              || size.width_pixels <= 0 || size.height_pixels <= 0 || size.width_pixels !== document.width || size.height_pixels !== document.height;
          })
          || !limits || limits.max_metadata_bytes !== 1048576 || limits.max_output_bytes !== comicPublicationMaxOutputBytes
          || !Number.isSafeInteger(limits.total_page_pixels) || limits.total_page_pixels !== totalPagePixels
          || !Number.isSafeInteger(limits.reserved_metadata_bytes) || limits.reserved_metadata_bytes < 1 || limits.reserved_metadata_bytes > limits.max_metadata_bytes
          || !Number.isSafeInteger(limits.reserved_output_bytes) || limits.reserved_output_bytes > limits.max_output_bytes
          || limits.reserved_output_bytes !== totalPagePixels * 4 + orderedPages.length * 65536 + limits.reserved_metadata_bytes + 65536) return invalidPublication();
      }
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
      if (checked.format === 'JPEG' || checked.format === 'WEBP') {
        const archive = checked.report, limits = archive.page_archive_limits;
        const requiredLoss = lossMode === 'LOSSLESS' ? 'PIXEL_EXACT_FLATTENED_RGB_ONLY' : 'LOSSY_PIXELS_INCLUDING_QUALITY_100';
        if (archive.format !== 'comic-page-archive-v1' || !validComicPageArchiveOptions(archive) || archive.image_format !== format
          || archive.loss_mode !== lossMode || archive.quality !== archiveOptions.quality || ![...archiveLosses, requiredLoss].every(loss => archive.losses.includes(loss))
          || !limits || Object.entries(comicPageArchiveLimits).some(([key, value]) => limits[key as keyof typeof comicPageArchiveLimits] !== value)
          || limits.total_page_pixels !== totalPagePixels || limits.reserved_codec_work_bytes !== totalPagePixels * 256 + orderedPages.length * 8 * 1024 * 1024
          || limits.reserved_output_bytes !== totalPagePixels * 8 + orderedPages.length * 65536 + 4 * 1024 * 1024) return invalidPublication();
      }
      return checked;
    }, (checked, ticket) => setReview({ ...checked, epoch: ticket, ownerRevision: live.current.getOwnerRevision() }));
  };

  return <section aria-label={`漫画书 ${format} 导出`}>
    <h3>出版副本 · {format}</h3>
    <Badge>合成图片阅读副本</Badge>
    <Field label="出版副本格式"><select value={format} disabled={props.disabled || busy} onChange={event => {
      if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === format || !['CBZ', 'PDF', 'EPUB', 'JPEG', 'WEBP'].includes(event.target.value)) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); setFormat(event.target.value as PublicationFormat);
      setLossMode(event.target.value === 'JPEG' ? 'LOSSY' : ''); setQuality(''); setLanguage('');
    }}><option value="CBZ">CBZ · 合成 PNG 图片</option><option value="PDF">PDF · 合成 RGB 栅格图片</option><option value="EPUB">EPUB · 固定版式合成 PNG 图片</option><option value="JPEG">JPEG 页面 · ZIP 阅读副本</option><option value="WEBP">WebP 页面 · ZIP 阅读副本</option></select></Field>
    {format === 'CBZ'
      ? <p>按已保存的章节和页面顺序导出合成 PNG。文字和图层不再可编辑；不包含 DPI、出血或印刷合规保证，外部阅读器兼容性尚未验证。请自行核对原图片授权，导出不会授予出版权利。</p>
      : format === 'PDF' ? <><p>按已保存的章节和页面顺序导出合成 RGB 栅格 PDF。文字和图层不再可编辑；DPI 仅确定页面尺寸，不提高图片分辨率或保证印刷质量。不包含出血，也不保证 PDF/A 或 PDF/X 合规。外部阅读器兼容性尚未验证，请自行核对原图片授权。</p>
        <p>PDF 是有容量限制的阅读副本：每次请求总页面像素约 270 万以内，页面开销会进一步降低额度。高分辨率或多页漫画书可能被拒绝；降低 DPI 不会降低原页面像素用量。</p></>
        : format === 'EPUB' ? <><p>按已保存的章节和页面顺序导出固定版式 EPUB 3，仅包含合成 RGB PNG 栅格图片。文字无法搜索或编辑；无文字替代内容，无障碍支持有限。不包含 DPI、出血、色彩配置文件或印刷保证，请自行核对原图片授权。</p>
          <p>语言需要明确选择 Unspecified (und)，不会推断内容语言。独立 EPUBCheck 验收：NOT_RUN；外部阅读器验收：NOT_RUN。文件校验不代表 EPUBCheck 或阅读器验收通过。</p>
          <p>EPUB 文件最多 64 MiB，元数据最多 1 MiB。导出前按总页面像素 × 4 字节 + 每页 65,536 字节 + 元数据预留 + 65,536 字节进行保守准入估算，超过 64 MiB 即拒绝。实际可导出页数取决于页面尺寸和标题开销；100 页书结构上限不保证可导出 100 张高分辨率页面。</p></>
        : <><p>按已保存的章节和页面顺序，将合成 RGB 页面编码为 {format === 'WEBP' ? 'WebP' : 'JPEG'} 图片并打包为 ZIP 阅读副本。文字和图层不再可编辑；不保留原色彩配置文件，不保证色彩或印刷保真。外部阅读器兼容性尚未验证，请自行核对原图片授权。</p>
          <p>JPEG 始终有损，质量 100 仍会改变像素。WebP 有损模式的质量 100 也不保证像素一致；WebP 无损仅保证与本次合成 RGB 页面像素完全一致，不恢复原图片、透明度、色彩配置文件或可编辑内容。</p>
          <p>ZIP 阅读副本限制：总页面像素最多 1,048,576（可容纳一张 1024 × 1024 页面），最多 8 页，单边最多 2048 px。编码工作额度 512 MiB，文件最多 64 MiB；降低质量不会减少页面像素用量。当前共 {totalPagePixels.toLocaleString('en-US')} 像素。</p></>}
    <p>当前已保存书结构 v{props.book.version} · {orderedPages.length} 页。阅读方向仅写入元数据，不重排页面、不镜像格框，也不保证阅读器采用该方向。</p>
    <ol aria-label={`${format} 已保存页面顺序`}>{orderedPages.map(({ id, chapterIndex, pageIndex, chapterTitle, page }) => <li key={id}>
      {page && !page.stale && page.document ? `${chapterIndex + 1}.${pageIndex + 1} · ${chapterTitle} · ${page.document.title} · v${page.version}` : '页面不可用'}
    </li>)}</ol>
    {props.disabled && <StatusMessage tone="warning">请先保存或放弃书结构与页面修改，并等待其他操作结束，再检查出版副本。</StatusMessage>}
    {!allApproved && <StatusMessage tone="warning">{format} 需要至少一页，且所有页面均为当前已批准的独立 PAGE 页面。请逐页完成预检与审核；WEBTOON 页面不能用于此导出。</StatusMessage>}
    {!props.client.postBlob && <StatusMessage tone="warning">当前入口不支持经过文件校验的 {format} 下载。</StatusMessage>}
    {isArchive && !archiveWithinLimits && <StatusMessage tone="warning">当前页面超出 ZIP 阅读副本容量限制，请使用符合上述页数、单边尺寸和总像素限制的已保存漫画书。</StatusMessage>}
    <Field label={`${format} 阅读方向`}><select value={direction} disabled={props.disabled || busy} onChange={event => {
      if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === direction || !['', 'LTR', 'RTL'].includes(event.target.value)) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); setDirection(event.target.value as ComicReadingDirection | '');
    }}><option value="">明确选择阅读方向</option><option value="LTR">从左到右（LTR）</option><option value="RTL">从右到左（RTL）</option></select></Field>
    {format === 'EPUB' && <Field label="EPUB 内容语言（需明确选择）"><select value={language} disabled={props.disabled || busy} onChange={event => {
      if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === language || !['', 'und'].includes(event.target.value)) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); setLanguage(event.target.value as '' | 'und');
    }}><option value="">明确选择内容语言</option><option value="und">Unspecified (und) · 未指定语言</option></select></Field>}
    {format === 'PDF' && <>
      <Field label="PDF DPI（36–600 整数，需明确填写）"><input type="number" min={36} max={600} step={1} value={dpi} disabled={props.disabled || busy} onChange={event => {
        if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === dpi) return;
        epoch.current++; clearReview(); setError(undefined); setNotice(''); setDpi(event.target.value);
      }} /></Field>
      <p>请根据目标页面尺寸选择 DPI，没有默认印刷质量。PDF 页面尺寸（pt）= 像素尺寸 × 72 ÷ DPI。</p>
      {dpi !== '' && !dpiValid && <StatusMessage tone="warning">PDF DPI 必须是 36–600 的整数。</StatusMessage>}
    </>}
    {isArchive && <>
      {format === 'WEBP' ? <Field label="WebP 编码模式"><select value={lossMode} disabled={props.disabled || busy} onChange={event => {
        if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === lossMode || !['', 'LOSSY', 'LOSSLESS'].includes(event.target.value)) return;
        epoch.current++; clearReview(); setError(undefined); setNotice(''); setLossMode(event.target.value as typeof lossMode); setQuality('');
      }}><option value="">明确选择编码模式</option><option value="LOSSY">有损 · 需选择质量</option><option value="LOSSLESS">无损 · 仅合成 RGB 像素一致</option></select></Field> : <p>JPEG 编码模式：有损（LOSSY）</p>}
      {lossMode === 'LOSSY' && <Field label={`${format} 有损质量`}><select value={quality} disabled={props.disabled || busy} onChange={event => {
        if (!current() || live.current.disabled || pending.current !== undefined || event.target.value === quality || !['', '60', '80', '95', '100'].includes(event.target.value)) return;
        epoch.current++; clearReview(); setError(undefined); setNotice(''); setQuality(event.target.value);
      }}><option value="">明确选择有损质量</option><option value="60">60</option><option value="80">80</option><option value="95">95</option><option value="100">100 · 仍然有损</option></select></Field>}
      {lossMode === 'LOSSLESS' && <p>WebP 无损模式不设置有损质量；请求中的质量值为 null。</p>}
    </>}
    <Button disabled={props.disabled || busy || !allApproved || !direction || (format === 'EPUB' && !epubOptionsValid) || (format === 'PDF' && !dpiValid) || (isArchive && (!archiveOptionsValid || !archiveWithinLimits)) || !props.client.postBlob} onClick={check}>检查当前漫画书出版副本</Button>
    {busy && <StatusMessage>正在检查或生成 {format}…放弃结果不会终止已发出的服务器处理。</StatusMessage>}
    {!!error && <ErrorMessage error={error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {reviewCurrent && <>
      <p>已检查 {review!.report.page_count} 页 · {review!.report.reading_direction} · 书结构 v{review!.report.book_version}</p>
      {review!.format === 'EPUB' && <>
        <p>已核对 EPUB · 固定版式 · Unspecified (und) · {review!.report.epub_limits.total_page_pixels.toLocaleString('en-US')} 像素</p>
        <ol aria-label="EPUB 已检查页面尺寸">{review!.report.page_dimensions.map((size, index) => <li key={index}>
          第 {index + 1} 页 · {size.width_pixels} × {size.height_pixels} px
        </li>)}</ol>
      </>}
      {review!.format === 'PDF' && <>
        <p>已核对 PDF · {review!.report.dpi} DPI</p>
        <ol aria-label="PDF 已检查页面尺寸">{review!.report.page_dimensions.map((size, index) => <li key={index}>
          第 {index + 1} 页 · {size.width_pixels} × {size.height_pixels} px · {size.width_points.toFixed(3)} × {size.height_points.toFixed(3)} pt
        </li>)}</ol>
      </>}
      {(review!.format === 'JPEG' || review!.format === 'WEBP') && <p>已核对 {review!.report.image_format} ZIP · {review!.report.loss_mode === 'LOSSLESS' ? '无损 · 仅合成 RGB 像素一致' : `有损 · 质量 ${review!.report.quality}`} · {review!.report.page_archive_limits.total_page_pixels.toLocaleString('en-US')} 像素</p>}
      <ul aria-label={`${format} 导出限制`}>{review!.report.losses.map((loss, index) => <li key={index}>{format === 'EPUB' && loss === 'EXTERNAL_READER_VALIDATION_NOT_RUN' ? '外部阅读器验收：NOT_RUN' : lossLabels[loss] || loss}</li>)}</ul>
      <label className="experimental-check"><input type="checkbox" checked={ack && acknowledged.current} onChange={event => {
        if (!admitted() || !reviewCurrent) return;
        acknowledged.current = event.target.checked; setAck(event.target.checked);
      }} />{format === 'EPUB' ? '已核对以上已保存页面顺序、阅读方向、未指定语言、固定版式尺寸及 EPUB 栅格与无障碍限制' : isArchive ? '已核对以上已保存页面顺序、阅读方向、编码格式、损失模式、质量与 ZIP 阅读副本限制' : format === 'PDF' ? '已核对以上已保存页面顺序、阅读方向、DPI、页面尺寸与合成图片限制' : '已核对以上已保存页面顺序、阅读方向与合成图片限制'}</label>
      <Button disabled={busy || !ack || !acknowledged.current} onClick={() => {
        if (!reviewCurrent || !review || !acknowledged.current) return;
        void run(() => review.format === 'EPUB' ? api.downloadEpub(props.book, review.report) : review.format === 'PDF' ? api.downloadPdf(props.book, review.report) : review.format === 'CBZ' ? api.downloadCbz(props.book, review.report) : api.downloadPageArchive(props.book, review.report), blob => {
          const archive = review.format === 'JPEG' || review.format === 'WEBP';
          saveOtioFile(blob, archive ? `comic-book-${review.format.toLowerCase()}.zip` : `comic-book.${review.format.toLowerCase()}`); setNotice(archive ? `已校验并下载 ${review.format} 页面 ZIP 阅读副本。` : `已校验并下载 ${review.format} 合成图片副本。`);
        });
      }}>下载已核对的 {format}{isArchive ? ' ZIP' : ''}</Button>
    </>}
    {(busy || reviewCurrent) && <Button onClick={() => {
      if (!current()) return;
      epoch.current++; clearReview(); setError(undefined); setNotice(''); if (pending.current !== undefined) release(pending.current);
    }}>放弃本次出版结果</Button>}
  </section>;
}
