import { comicLayersError, duplicateComicLayers } from './comicLayers';
import type { ComicCatalog, ComicDocument, ComicPanel, ComicRect } from './comicLayoutsClient';

export type ComicDuplicateTarget = { sourceId: string; x: number; y: number };
export type ComicDuplicatePreview = { panel?: ComicPanel; error?: string };
const integer = (n: number, min: number, max: number) => Number.isInteger(n) && n >= min && n <= max;
const id = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value);
const rect = (r: ComicRect) => r && integer(r.x, 0, 12000) && integer(r.y, 0, 12000) && integer(r.width, 16, 1600) && integer(r.height, 16, 12000);
const inside = (a: ComicRect, b: ComicRect, pad: number) => a.x >= b.x + pad && a.y >= b.y + pad && a.x + a.width <= b.x + b.width - pad && a.y + a.height <= b.y + b.height - pad;
const overlaps = (a: ComicRect, b: ComicRect) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
const points = (s: string) => Array.from(s).length;

// No IDs, writes, pins, normalization or raster work during preview. Original
// save/preflight remains authoritative for permissions, text metrics and pixels.
export function previewComicDuplicate(document: ComicDocument, catalog: ComicCatalog, target: ComicDuplicateTarget): ComicDuplicatePreview {
  const fail = (error: string): ComicDuplicatePreview => ({ error });
  if (!document || !Array.isArray(document.panels) || !document.panels.length || document.panels.length >= 24) return fail('复制后最多 24 个格框。');
  if (!integer(document.width, 320, 1600) || !integer(document.height, 320, 12000) || document.width * document.height > 16000000 || !integer(document.safe_area, 0, 128) || !integer(document.segment_height, 320, 2400)) return fail('请先修正页面尺寸、安全区与分段高度。');
  const layerError = comicLayersError(document); if (layerError) return fail(layerError);
  const panels = document.panels;
  if (panels.some(p => !p || !id(p.id) || !Array.isArray(p.bubbles) || p.bubbles.length > 12 || p.bubbles.some(b => !b || !id(b.id) || typeof b.text !== 'string'))) return fail('格框或气泡结构无效。');
  if (panels.some(p => p.appearance_references !== undefined && (!Array.isArray(p.appearance_references) || p.appearance_references.some(ref => !ref || typeof ref !== 'object')))) return fail('外观引用结构无效，请重新打开有效布局。');
  const source = panels.find(p => p.id === target.sourceId);
  if (!source) return fail('请选择仍在草稿中的来源格框。');
  const ordered = [...panels].sort((a, b) => a.order - b.order);
  if (new Set(panels.map(p => p.id)).size !== panels.length || ordered.some((p, i) => p.order !== i + 1) || [...panels].sort((a, b) => a.y - b.y || a.x - b.x).some((p, i) => p !== ordered[i])) return fail('请先修正连续阅读顺序与位置；复制会追加在末尾。');
  const bubbles = panels.flatMap(p => p.bubbles);
  if (new Set(bubbles.map(b => b.id)).size !== bubbles.length || bubbles.length + source.bubbles.length > 80 || [...bubbles, ...source.bubbles].reduce((sum, b) => sum + points(b.text), 0) > 10000) return fail('复制后气泡总数不能超过 80，文字总数不能超过 10000，且标识不能重复。');
  if (bubbles.some(b => !integer(b.font_size, 14, 96) || !['DIALOGUE', 'NARRATION'].includes(b.kind) || points(b.text) < 1 || points(b.text) > 1000 || Array.from(b.text).some(c => { const n = c.codePointAt(0)!; return (n < 32 && c !== '\n') || (n >= 0xd800 && n <= 0xdfff); }))) return fail('请先修正气泡文字、字号或类型；不会改写文字。');
  const frame = { x: 0, y: 0, width: document.width, height: document.height };
  if (panels.some((p, i) => !rect(p) || !inside(p, frame, document.safe_area) || panels.slice(0, i).some(other => overlaps(p, other)) || p.bubbles.some((b, bi) => !rect(b) || !inside(b, p, 8) || p.bubbles.slice(0, bi).some(other => overlaps(b, other))))) return fail('请先修正原格框与气泡边界或重叠；气泡需保留 8 px 内边界。');
  const screenplay = catalog?.screenplays?.find(s => s.id === document.screenplay_id);
  if (document.source_mode === 'INDEPENDENT' && (document.screenplay_id != null || document.expected_screenplay_version != null || panels.some(p => p.shot_id != null))) return fail('独立漫画不能携带剧本或镜头绑定。');
  if (document.source_mode !== 'INDEPENDENT' && (!screenplay || screenplay.edit_version !== document.expected_screenplay_version || panels.some(p => !screenplay.shots.some(s => s.id === p.shot_id)))) return fail('来源剧本或镜头已变化，请刷新并核对。');
  const currentAsset = (assetId: string, version: number | null) => catalog.assets.some(a => a.id === assetId && a.version === version && a.approved);
  if (panels.some(p => !Array.isArray(p.character_ids) || p.character_ids.some(cid => !catalog.characters.some(c => c.id === cid)) || p.bubbles.some(b => b.character_id && !catalog.characters.some(c => c.id === b.character_id)) || (p.asset_id && !currentAsset(p.asset_id, p.expected_asset_version)) || (p.appearance_references || []).some(ref => !p.character_ids.includes(ref.character_id) || !currentAsset(ref.asset_id, ref.expected_asset_version)))) return fail('图片版本、批准状态或人物引用已变化，请刷新并核对；不会替换引用。');
  if (!['CONTAIN', 'COVER'].includes(source.fit) || [source.cover_x_percent, source.cover_y_percent].some(n => n !== undefined && !integer(n, 0, 100))) return fail('请先修正来源图片裁切位置。');
  const panel = { ...source, x: target.x, y: target.y, order: panels.length + 1, character_ids: [...source.character_ids], ...(source.appearance_references === undefined ? {} : { appearance_references: source.appearance_references.map(ref => ({ ...ref })) }), bubbles: source.bubbles.map(b => ({ ...b, x: b.x + target.x - source.x, y: b.y + target.y - source.y })) };
  if (!rect(panel) || !inside(panel, frame, document.safe_area)) return fail('目标位置超出页面安全区；请调整目标或页面，不会缩放或裁切内容。');
  if (panels.some(p => overlaps(panel, p))) return fail('目标位置与现有格框重叠，请选择空白位置。');
  const last = ordered[ordered.length - 1];
  if (panel.y < last.y || (panel.y === last.y && panel.x <= last.x)) return fail('新格框须位于现有阅读顺序之后（从上到下，同一行从左到右）。');
  return { panel };
}

// IDs are supplied once by the explicit apply intent, never minted on preview,
// rerender, undo/redo or inside a React state updater. Failures are atomic.
export function applyComicDuplicate(document: ComicDocument, catalog: ComicCatalog, target: ComicDuplicateTarget, ids: { panel: string; bubbles: string[] }): { document?: ComicDocument; error?: string } {
  const preview = previewComicDuplicate(document, catalog, target);
  if (!preview.panel) return { error: preview.error };
  const fresh = [ids.panel, ...ids.bubbles];
  const existing = new Set(document.panels.flatMap(p => [p.id, ...p.bubbles.map(b => b.id)]));
  if (ids.bubbles.length !== preview.panel.bubbles.length || fresh.some(value => !id(value) || existing.has(value)) || new Set(fresh).size !== fresh.length) return { error: '新格框或气泡标识冲突，请重新预览后再应用。' };
  const panel = { ...preview.panel, id: ids.panel, bubbles: preview.panel.bubbles.map((b, i) => ({ ...b, id: ids.bubbles[i] })) };
  try {
    const source = document.panels.find(p => p.id === target.sourceId)!;
    return { document: duplicateComicLayers(document, { ...document, panels: [...document.panels, panel] }, source.id, panel.id, new Map(source.bubbles.map((bubble, index) => [bubble.id, panel.bubbles[index].id]))) };
  } catch (error) { return { error: error instanceof Error ? error.message : '无法复制图层；草稿未改变。' }; }
}
