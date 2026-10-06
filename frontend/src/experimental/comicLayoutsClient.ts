import type { ExperimentalClient } from './api';
import type { DirectorScreenplay } from './directorClient';
import type { RefNode } from '../novel/useMultimodalWorkspacePersistence';
// Original canvas coordinate/identity contract, with explicit print dimensions.
export type ComicRect = Pick<RefNode, 'x' | 'y'> & { width: number; height: number };
export type ComicBubble = ComicRect & { id: string; kind: 'DIALOGUE' | 'NARRATION'; text: string; character_id: string | null; font_size: number };
export type ComicPanel = ComicRect & { id: string; shot_id: string; order: number; character_ids: string[]; asset_id: string | null; expected_asset_version: number | null; fit: 'CONTAIN' | 'COVER'; bubbles: ComicBubble[] };
export type ComicDocument = { title: string; screenplay_id: string; expected_screenplay_version: number; preset: 'PAGE' | 'WEBTOON'; font_family: 'NOTO_SANS_SC_OFL'; width: number; height: number; safe_area: number; segment_height: number; panels: ComicPanel[] };
export type ComicRecord = { id: string; version: number; status: string; stale: boolean; document?: ComicDocument; history_versions?: number[]; scene_ids?: Record<string, string> };
export type ComicAsset = { id: string; filename: string; version: number; approved: boolean; manual_review_available: boolean };
export type ComicCatalog = { screenplays: DirectorScreenplay[]; characters: { id: string; name: string }[]; assets: ComicAsset[]; presets: Record<'PAGE' | 'WEBTOON', { width: number; height: number; safe_area: number; segment_height: number }>; renderer: { available: boolean; code?: string }; font: { available: boolean; code?: string } };
export type ComicPreflight = { issues: { code: string; target: string; severity: string }[]; segments: { index: number; width: number; height: number; y: number }[]; can_render: boolean; review_digest: string; version: number; status: string };
const path = (row: ComicRecord) => `/comic-layouts/records/${encodeURIComponent(row.id)}`;
export function comicLayoutsClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<ComicCatalog>('/comic-layouts/catalog', signal),
    records: (signal?: AbortSignal) => client.get<{ items: ComicRecord[] }>('/comic-layouts/records', signal),
    image: (id: string) => client.blob(`/comic-layouts/images/${encodeURIComponent(id)}`),
    approveImage: (asset: ComicAsset) => client.post(`/comic-layouts/images/${encodeURIComponent(asset.id)}/approve`, { expected_version: asset.version }),
    save: (doc: ComicDocument, row?: ComicRecord) => row ? client.put<ComicRecord>(path(row), { ...doc, expected_version: row.version }) : client.post<ComicRecord>('/comic-layouts/records', doc),
    preflight: (row: ComicRecord) => client.post<ComicPreflight>(path(row) + '/preflight', { expected_version: row.version }),
    approve: (row: ComicRecord, report: ComicPreflight) => client.post<ComicRecord>(path(row) + '/approve', { expected_version: row.version, review_digest: report.review_digest, acknowledge_warnings: true }),
    restore: (row: ComicRecord, target_version: number) => client.post<ComicRecord>(path(row) + '/restore', { expected_version: row.version, target_version }),
    segment: (row: ComicRecord, index: number) => client.blob(path(row) + `/segments/${index}?expected_version=${row.version}`),
    download: (row: ComicRecord) => client.blob(path(row) + `/export?expected_version=${row.version}`),
  };
}
export const comicIssueLabel: Record<string, string> = {
  COMIC_SPATIAL_ORDER_CONFLICT: '支持从上到下、同一行从左到右的顺序；编号与位置冲突', COMIC_MISSING_APPROVED_IMAGE: '缺少已批准图片', COMIC_READING_ORDER_CONFLICT: '阅读顺序必须从 1 连续编号，不能重复', COMIC_PANEL_OUTSIDE_SAFE_AREA: '格框超出页面安全区', COMIC_PANEL_OVERLAP: '格框重叠',
  COMIC_BUBBLE_OUTSIDE_PANEL_SAFE_AREA: '气泡超出格框内的 8 px 安全区', COMIC_BUBBLE_OVERLAP: '气泡重叠', COMIC_TEXT_OVERFLOW: '文字超出气泡，请扩大气泡或精简文字',
  COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE: '缺少已校验的 OFL 中文字体，不能渲染文字', COMIC_FONT_MISSING_GLYPH: '字体缺少所需字形，禁止以方框代替', COMIC_CENTER_CROP: '居中填满会裁切图片，请核对画面',
  COMIC_SEGMENT_CUTS_BUBBLE: '分段边界切过气泡，请检查拼接或调整位置', COMIC_SMALL_TEXT_AT_320PX: '320 px 屏宽下文字小于 12 px，请检查可读性', COMIC_IMAGE_RESAMPLE_LIMIT: '图片比例极端，缩放会超出内存上限',
  COMIC_RENDERER_UNAVAILABLE: '未安装漫画栅格渲染组件', COMIC_PINNED_PILLOW_REQUIRED: '渲染组件版本未通过校验',
};
export function comicPreset(source: DirectorScreenplay, preset: 'PAGE' | 'WEBTOON', settings: ComicCatalog['presets']['PAGE']): ComicDocument {
  const shots = source.shots.slice(0, preset === 'PAGE' ? 4 : 6); const gap = 16; const inset = settings.safe_area;
  const height = Math.floor((settings.height - inset * 2 - (shots.length - 1) * gap) / Math.max(1, shots.length));
  return { title: `${source.title} · 漫画草稿`, screenplay_id: source.id, expected_screenplay_version: source.edit_version, preset, font_family: 'NOTO_SANS_SC_OFL', ...settings,
    panels: shots.map((shot, i) => ({ id: `panel-${i + 1}`, shot_id: shot.id, order: i + 1, x: inset, y: inset + i * (height + gap), width: settings.width - inset * 2, height, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', bubbles: [] })) };
}
