import type { ExperimentalClient } from './api';
import { ApiError } from '../api';
import type { DirectorScreenplay } from './directorClient';
import type { RefNode } from '../novel/useMultimodalWorkspacePersistence';
// Original canvas coordinate/identity contract, with explicit print dimensions.
export type ComicRect = Pick<RefNode, 'x' | 'y'> & { width: number; height: number };
export type ComicBubble = ComicRect & { id: string; kind: 'DIALOGUE' | 'NARRATION'; text: string; character_id: string | null; font_size: number; text_align?: 'LEFT' | 'CENTER' | 'RIGHT'; line_height_percent?: number };
export type ComicAppearanceReference = { character_id: string; asset_id: string; expected_asset_version: number; note: string };
export type ComicPanel = ComicRect & { id: string; shot_id: string | null; artwork_mode?: 'IMAGE' | 'BLANK'; order: number; character_ids: string[]; asset_id: string | null; expected_asset_version: number | null; fit: 'CONTAIN' | 'COVER'; cover_x_percent?: number; cover_y_percent?: number; bubbles: ComicBubble[]; image_brief?: string; appearance_references?: ComicAppearanceReference[] };
export type ComicNativeLayerKind = 'PANEL_ART' | 'PANEL_FRAME' | 'BUBBLE_SHAPE' | 'BUBBLE_TEXT';
export type ComicLayerKind = ComicNativeLayerKind | 'RASTER';
type ComicLayerBase = { id: string; target_id: string; name: string; visible: boolean; opacity_percent: number };
export type ComicNativeLayer = ComicLayerBase & { kind: ComicNativeLayerKind };
export type ComicRasterLayer = ComicLayerBase & ComicRect & { kind: 'RASTER'; pin: { version: number; sha256: string; review_digest: string } };
export type ComicLayer = ComicNativeLayer | ComicRasterLayer;
/** Items are stored bottom-to-top. Text and geometry remain on their canonical objects. */
export type ComicLayerStack = { schema_version: 1; items: ComicLayer[] };
export type ComicDocument = { layer_stack?: ComicLayerStack; title: string; source_mode?: 'SCREENPLAY' | 'INDEPENDENT'; screenplay_id: string | null; expected_screenplay_version: number | null; preset: 'PAGE' | 'WEBTOON'; font_family: 'NOTO_SANS_SC_OFL'; width: number; height: number; safe_area: number; segment_height: number; panels: ComicPanel[] };
export type ComicRecord = { id: string; version: number; status: string; stale: boolean; document?: ComicDocument; history_versions?: number[]; scene_ids?: Record<string, string> };
export type ComicChapter = { id: string; title: string; pages: string[] };
export type ComicBookDocument = { title: string; chapters: ComicChapter[] };
export type ComicBook = { id: string; version: number; stale: boolean; title?: string; chapters?: ComicChapter[]; history_versions?: number[] };
export type ComicBookPageResult = { book: ComicBook; page: ComicRecord };
export type ComicReadingDirection = 'LTR' | 'RTL';
export type ComicPublicationPage = { id: string; version: number; review_digest: string };
export type ComicPublicationPreflight = { book_version: number; reading_direction: ComicReadingDirection; pages: ComicPublicationPage[]; publication_digest: string; page_count: number; losses: string[] };
export type ComicEpubOptions = { format: 'comic-epub-fixed-raster-v1'; language: 'und' };
export type ComicEpubLimits = { max_metadata_bytes: number; max_output_bytes: number; total_page_pixels: number; reserved_metadata_bytes: number; reserved_output_bytes: number };
export type ComicEpubPublicationPreflight = ComicPublicationPreflight & ComicEpubOptions & { page_dimensions: { width_pixels: number; height_pixels: number }[]; epub_limits: ComicEpubLimits };
export const comicPublicationMaxOutputBytes = 64 * 1024 * 1024;
export type ComicPdfPageDimensions = { width_pixels: number; height_pixels: number; width_points: number; height_points: number };
export type ComicPdfPublicationPreflight = ComicPublicationPreflight & { format: 'comic-pdf-raster-v1'; dpi: number; page_dimensions: ComicPdfPageDimensions[] };
export type ComicPageArchiveQuality = 60 | 80 | 95 | 100;
export type ComicPageArchiveOptions = { image_format: 'JPEG' | 'WEBP'; loss_mode: 'LOSSY'; quality: ComicPageArchiveQuality } | { image_format: 'WEBP'; loss_mode: 'LOSSLESS'; quality: null };
export type ComicPageArchiveLimits = { max_total_page_pixels: number; max_pages: number; max_side_pixels: number; max_codec_work_bytes: number; max_output_bytes: number; total_page_pixels: number; reserved_codec_work_bytes: number; reserved_output_bytes: number };
export type ComicPageArchivePreflight = ComicPublicationPreflight & ComicPageArchiveOptions & { format: 'comic-page-archive-v1'; page_archive_limits: ComicPageArchiveLimits };
export const comicPageArchiveLimits = { max_total_page_pixels: 1048576, max_pages: 8, max_side_pixels: 2048, max_codec_work_bytes: 536870912, max_output_bytes: 67108864 } as const;
export type ComicAsset = { id: string; filename: string; version: number; approved: boolean; manual_review_available: boolean };
export type ComicCatalog = { screenplays: DirectorScreenplay[]; characters: { id: string; name: string }[]; assets: ComicAsset[]; presets: Record<'PAGE' | 'WEBTOON', { width: number; height: number; safe_area: number; segment_height: number }>; renderer: { available: boolean; code?: string }; font: { available: boolean; code?: string } };
export type ComicPreflight = { issues: { code: string; target: string; severity: string }[]; segments: { index: number; width: number; height: number; y: number }[]; can_render: boolean; review_digest: string; version: number; status: string };
const path = (row: ComicRecord) => `/comic-layouts/records/${encodeURIComponent(row.id)}`;
export function comicLayoutsClient(client: ExperimentalClient) {
  return {
    books: (signal?: AbortSignal) => client.get<{ items: ComicBook[] }>('/comic-layouts/books', signal),
    createBook: (title: string) => client.post<ComicBook>('/comic-layouts/books', { title, chapters: [] }),
    saveBook: (book: ComicBook, document: ComicBookDocument, expected_page_versions: Record<string, number>) => client.put<ComicBook>(`/comic-layouts/books/${encodeURIComponent(book.id)}`, { ...document, expected_version: book.version, expected_page_versions }),
    createBookPage: (book: ComicBook, chapter_id: string, source?: ComicRecord) => client.post<ComicBookPageResult>(`/comic-layouts/books/${encodeURIComponent(book.id)}/pages`, { expected_version: book.version, chapter_id, ...(source ? { source_layout_id: source.id, expected_source_version: source.version } : {}) }),
    restoreBook: (book: ComicBook, target_version: number) => client.post<ComicBook>(`/comic-layouts/books/${encodeURIComponent(book.id)}/restore`, { expected_version: book.version, target_version }),
    publicationPreflight: (book: ComicBook, reading_direction: ComicReadingDirection) => client.post<ComicPublicationPreflight>(`/comic-layouts/books/${encodeURIComponent(book.id)}/publication-preflight`, { expected_version: book.version, reading_direction }),
    pdfPublicationPreflight: (book: ComicBook, reading_direction: ComicReadingDirection, dpi: number) => {
      if (!validComicPdfDpi(dpi)) return invalidPublication();
      return client.post<ComicPdfPublicationPreflight>(`/comic-layouts/books/${encodeURIComponent(book.id)}/pdf-publication-preflight`, { expected_version: book.version, reading_direction, dpi });
    },
    epubPublicationPreflight: (book: ComicBook, reading_direction: ComicReadingDirection, options: ComicEpubOptions) => {
      if (!validComicEpubOptions(options) || !validComicReadingDirection(reading_direction)) return invalidPublication();
      return client.post<ComicEpubPublicationPreflight>(`/comic-layouts/books/${encodeURIComponent(book.id)}/epub-publication-preflight`, {
        expected_version: book.version, reading_direction, format: options.format, language: options.language,
      });
    },
    downloadEpub: async (book: ComicBook, report: ComicEpubPublicationPreflight) => {
      if (!client.postBlob || !report || book.version !== report.book_version || !validComicEpubOptions(report) || !validComicReadingDirection(report.reading_direction)
        || !Array.isArray(report.pages) || report.pages.length < 1 || report.pages.length > 100 || report.page_count !== report.pages.length
        || new Set(report.pages.map(page => page?.id)).size !== report.pages.length
        || report.pages.some(page => !page || typeof page.id !== 'string' || !page.id || !Number.isSafeInteger(page.version) || page.version < 1 || !/^[a-f0-9]{64}$/.test(page.review_digest))
        || !/^[a-f0-9]{64}$/.test(report.publication_digest)) return invalidPublication();
      const { blob, headers } = await client.postBlob(`/comic-layouts/books/${encodeURIComponent(book.id)}/export-epub`, {
        expected_version: report.book_version, reading_direction: report.reading_direction, format: report.format, language: report.language,
        pages: report.pages.map(({ id, version, review_digest }) => ({ id, version, review_digest })), publication_digest: report.publication_digest,
      }, { maxBytes: comicPublicationMaxOutputBytes });
      const sha256 = headers.get('X-Content-SHA256');
      if (blob.type.split(';')[0] !== 'application/epub+zip' || !blob.size || blob.size > comicPublicationMaxOutputBytes || headers.get('X-Comic-Publication-Digest') !== report.publication_digest || !sha256 || !/^[a-f0-9]{64}$/.test(sha256)) return invalidPublication();
      const digest = await globalThis.crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
      if (Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('') !== sha256) return invalidPublication();
      return blob;
    },
    pageArchivePreflight: (book: ComicBook, reading_direction: ComicReadingDirection, options: ComicPageArchiveOptions) => {
      if (!validComicPageArchiveOptions(options)) return invalidPublication();
      return client.post<ComicPageArchivePreflight>(`/comic-layouts/books/${encodeURIComponent(book.id)}/page-archive-preflight`, {
        expected_version: book.version, reading_direction, image_format: options.image_format, loss_mode: options.loss_mode, quality: options.quality,
      });
    },
    downloadPageArchive: async (book: ComicBook, report: ComicPageArchivePreflight) => {
      if (!client.postBlob || book.version !== report.book_version || report.format !== 'comic-page-archive-v1' || !validComicPageArchiveOptions(report)) return invalidPublication();
      const { blob, headers } = await client.postBlob(`/comic-layouts/books/${encodeURIComponent(book.id)}/export-page-archive`, {
        expected_version: report.book_version, reading_direction: report.reading_direction,
        image_format: report.image_format, loss_mode: report.loss_mode, quality: report.quality,
        pages: report.pages.map(({ id, version, review_digest }) => ({ id, version, review_digest })), publication_digest: report.publication_digest,
      }, { maxBytes: comicPageArchiveLimits.max_output_bytes });
      const sha256 = headers.get('X-Content-SHA256');
      if (blob.type.split(';')[0] !== 'application/zip' || !blob.size || blob.size > comicPageArchiveLimits.max_output_bytes || headers.get('X-Comic-Publication-Digest') !== report.publication_digest || !sha256 || !/^[a-f0-9]{64}$/.test(sha256)) return invalidPublication();
      const digest = await globalThis.crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
      if (Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('') !== sha256) return invalidPublication();
      return blob;
    },
    downloadCbz: async (book: ComicBook, report: ComicPublicationPreflight) => {
      if (!client.postBlob || book.version !== report.book_version) return invalidPublication();
      const { blob, headers } = await client.postBlob(`/comic-layouts/books/${encodeURIComponent(book.id)}/export-cbz`, {
        expected_version: report.book_version, reading_direction: report.reading_direction,
        pages: report.pages.map(({ id, version, review_digest }) => ({ id, version, review_digest })), publication_digest: report.publication_digest,
      }, { maxBytes: comicPublicationMaxOutputBytes });
      const sha256 = headers.get('X-Content-SHA256');
      if (blob.type.split(';')[0] !== 'application/vnd.comicbook+zip' || !blob.size || blob.size > comicPublicationMaxOutputBytes || headers.get('X-Comic-Publication-Digest') !== report.publication_digest || !sha256 || !/^[a-f0-9]{64}$/.test(sha256)) return invalidPublication();
      const digest = await globalThis.crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
      if (Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('') !== sha256) return invalidPublication();
      return blob;
    },
    downloadPdf: async (book: ComicBook, report: ComicPdfPublicationPreflight) => {
      if (!client.postBlob || book.version !== report.book_version || report.format !== 'comic-pdf-raster-v1' || !validComicPdfDpi(report.dpi)) return invalidPublication();
      const { blob, headers } = await client.postBlob(`/comic-layouts/books/${encodeURIComponent(book.id)}/export-pdf`, {
        expected_version: report.book_version, reading_direction: report.reading_direction, dpi: report.dpi,
        pages: report.pages.map(({ id, version, review_digest }) => ({ id, version, review_digest })), publication_digest: report.publication_digest,
      }, { maxBytes: comicPublicationMaxOutputBytes });
      const sha256 = headers.get('X-Content-SHA256');
      if (blob.type.split(';')[0] !== 'application/pdf' || !blob.size || blob.size > comicPublicationMaxOutputBytes || headers.get('X-Comic-Publication-Digest') !== report.publication_digest || !sha256 || !/^[a-f0-9]{64}$/.test(sha256)) return invalidPublication();
      const digest = await globalThis.crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
      if (Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('') !== sha256) return invalidPublication();
      return blob;
    },
    catalog: (signal?: AbortSignal) => client.get<ComicCatalog>('/comic-layouts/catalog', signal),
    records: (signal?: AbortSignal) => client.get<{ items: ComicRecord[] }>('/comic-layouts/records', signal),
    image: (id: string) => client.blob(`/comic-layouts/images/${encodeURIComponent(id)}`),
    approveImage: (asset: ComicAsset) => client.post(`/comic-layouts/images/${encodeURIComponent(asset.id)}/approve`, { expected_version: asset.version }),
    save: (doc: ComicDocument, row?: ComicRecord) => row ? client.put<ComicRecord>(path(row), { ...doc, expected_version: row.version }) : client.post<ComicRecord>('/comic-layouts/records', doc),
    preflight: (row: ComicRecord) => client.post<ComicPreflight>(path(row) + '/preflight', { expected_version: row.version }),
    approve: (row: ComicRecord, report: ComicPreflight) => client.post<ComicRecord>(path(row) + '/approve', { expected_version: row.version, review_digest: report.review_digest, acknowledge_warnings: true }),
    restore: (row: ComicRecord, target_version: number) => client.post<ComicRecord>(path(row) + '/restore', { expected_version: row.version, target_version }),
    segment: (row: ComicRecord, index: number) => client.blob(path(row) + `/segments/${index}?expected_version=${row.version}`),
    downloadOra: (row: ComicRecord) => client.blob(path(row) + `/export-ora?expected_version=${row.version}`),
    download: (row: ComicRecord) => client.blob(path(row) + `/export?expected_version=${row.version}`),
  };
}
export function validComicReadingDirection(direction: unknown): direction is ComicReadingDirection { return direction === 'LTR' || direction === 'RTL'; }
export function validComicEpubOptions(options: { format: unknown; language: unknown } | null | undefined): options is ComicEpubOptions {
  return !!options && options.format === 'comic-epub-fixed-raster-v1' && options.language === 'und';
}
export function validComicPdfDpi(dpi: number): boolean { return Number.isInteger(dpi) && dpi >= 36 && dpi <= 600; }
export function validComicPageArchiveOptions(options: { image_format: unknown; loss_mode: unknown; quality: unknown } | null | undefined): options is ComicPageArchiveOptions {
  return !!options && (options.image_format === 'JPEG' || options.image_format === 'WEBP')
    && (options.loss_mode === 'LOSSLESS' ? options.image_format === 'WEBP' && options.quality === null
      : options.loss_mode === 'LOSSY' && typeof options.quality === 'number' && [60, 80, 95, 100].includes(options.quality));
}
export function invalidPublication(): never {
  throw new ApiError({ status: 422, code: 'COMIC_PUBLICATION_INVALID_RESPONSE', message: '出版检查或文件校验与当前书不一致。请刷新书和页面，重新检查后再下载。' });
}
export const comicIssueLabel: Record<string, string> = {
  COMIC_SPATIAL_ORDER_CONFLICT: '支持从上到下、同一行从左到右的顺序；编号与位置冲突', COMIC_MISSING_APPROVED_IMAGE: '缺少已批准图片', COMIC_READING_ORDER_CONFLICT: '阅读顺序必须从 1 连续编号，不能重复', COMIC_PANEL_OUTSIDE_SAFE_AREA: '格框超出页面安全区', COMIC_PANEL_OVERLAP: '格框重叠',
  COMIC_BUBBLE_OUTSIDE_PANEL_SAFE_AREA: '气泡超出格框内的 8 px 安全区', COMIC_BUBBLE_OVERLAP: '气泡重叠', COMIC_TEXT_OVERFLOW: '文字超出气泡，请扩大气泡或精简文字',
  COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE: '缺少已校验的 OFL 中文字体，不能渲染文字', COMIC_FONT_MISSING_GLYPH: '字体缺少所需字形，禁止以方框代替', COMIC_CENTER_CROP: '居中填满会裁切图片，请核对画面', COMIC_POSITIONED_CROP: '按指定位置填满会裁切图片，请核对画面',
  COMIC_SEGMENT_CUTS_BUBBLE: '分段边界切过气泡，请检查拼接或调整位置', COMIC_SMALL_TEXT_AT_320PX: '320 px 屏宽下文字小于 12 px，请检查可读性', COMIC_IMAGE_RESAMPLE_LIMIT: '图片比例极端，缩放会超出内存上限',
  COMIC_RENDERER_UNAVAILABLE: '未安装漫画栅格渲染组件', COMIC_PINNED_PILLOW_REQUIRED: '渲染组件版本未通过校验',
};
export function comicPreset(source: DirectorScreenplay, preset: 'PAGE' | 'WEBTOON', settings: ComicCatalog['presets']['PAGE']): ComicDocument {
  const shots = source.shots.slice(0, preset === 'PAGE' ? 4 : 6); const gap = 16; const inset = settings.safe_area;
  const height = Math.floor((settings.height - inset * 2 - (shots.length - 1) * gap) / Math.max(1, shots.length));
  return { title: `${source.title} · 漫画草稿`, screenplay_id: source.id, expected_screenplay_version: source.edit_version, preset, font_family: 'NOTO_SANS_SC_OFL', ...settings,
    panels: shots.map((shot, i) => ({ id: `panel-${i + 1}`, shot_id: shot.id, order: i + 1, x: inset, y: inset + i * (height + gap), width: settings.width - inset * 2, height, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', bubbles: [], image_brief: '', appearance_references: [] })) };
}

/** An explicit authored page; never fabricate screenplay, shot or image bindings. */
export function blankComic(preset: 'PAGE' | 'WEBTOON', settings: ComicCatalog['presets']['PAGE']): ComicDocument {
  return { title: '空白漫画页', source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null, preset, font_family: 'NOTO_SANS_SC_OFL', ...settings, panels: [] };
}
