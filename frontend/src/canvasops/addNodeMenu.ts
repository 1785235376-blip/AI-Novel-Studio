/**
 * [HERMIA-FE-20261022] H-P1-03 · 双画布「加节点」最小菜单纯函数。
 * 只过滤现存目录；不新增节点类型、不抬执行预算、不把拖素材写成拷贝。
 */
import { graphCatalogForSchema } from '../creative/graphDraft';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphDefinitionId } from '../creative/studioGraphTypes';
import { filterNodes, nodeSearchIndex } from './canvasOps';
import type { CanvasCatalogEntry, CanvasCatalogMatch, CanvasNodeCategory } from './canvasOpsTypes';

/** 创作画布优先展示的角色分类（作品对象 / 引用 / 意图），执行画布优先可执行步骤。 */
export type AddNodeCanvasRole = 'creation' | 'execution' | 'all';

export const ADD_NODE_MIME_ASSET_REF = 'application/x-poemseed-asset-ref';

/** 拖入语义：仅引用，不复制文件、不自动开任务。 */
export type AddNodeAssetDropPayload = {
  asset_id: string;
  version: number;
  digest: string;
  kind: string;
};

const CREATION_CATEGORIES: ReadonlySet<CanvasNodeCategory> = new Set(['TEXT', 'ASSET', 'STORYBOARD', 'IMAGE']);
const EXECUTION_CATEGORIES: ReadonlySet<CanvasNodeCategory> = new Set(['MEDIA', 'VIDEO', 'TEXT']);

/** 选类型后仍需在原控件明确选来源的节点；最小菜单只选中类型，不静默添加。 */
export const ADD_NODE_NEEDS_SOURCE: ReadonlySet<StudioGraphDefinitionId> = new Set([
  'asset_reference', 'director_plan', 'storyboard_plan', 'storyboard_shot', 'timeline_export',
]);

export function parseAssetDropPayload(raw: string): AddNodeAssetDropPayload | null {
  if (!raw.trim()) return null;
  try {
    const row = JSON.parse(raw) as Record<string, unknown>;
    if (typeof row.asset_id !== 'string' || !row.asset_id.trim()) return null;
    if (!Number.isSafeInteger(row.version) || (row.version as number) < 1) return null;
    if (typeof row.digest !== 'string' || !row.digest.trim()) return null;
    if (typeof row.kind !== 'string' || !row.kind.trim()) return null;
    return { asset_id: row.asset_id, version: row.version as number, digest: row.digest, kind: row.kind };
  } catch {
    return null;
  }
}

export function serializeAssetDropPayload(payload: AddNodeAssetDropPayload): string {
  return JSON.stringify(payload);
}

function roleAllows(entry: CanvasCatalogEntry, role: AddNodeCanvasRole): boolean {
  if (role === 'all') return true;
  if (role === 'creation') {
    // 创作：作品/引用/意图类；asset_reference 始终保留（拖入＝引用）。
    if (entry.id === 'asset_reference') return true;
    return entry.categories.some(cat => CREATION_CATEGORIES.has(cat));
  }
  // 执行：可执行步骤优先；MEDIA/VIDEO 类也保留。
  if (entry.executable) return true;
  return entry.categories.some(cat => EXECUTION_CATEGORIES.has(cat));
}

/** 按画布角色 + 图格式过滤现存目录；不发明类型。 */
export function filterAddNodeTypes(
  catalog: StudioGraphCatalog | undefined,
  definition: StudioGraphDefinition,
  role: AddNodeCanvasRole,
  query = '',
): CanvasCatalogMatch[] {
  if (!catalog) return [];
  const allowed = new Set(graphCatalogForSchema(catalog.definitions, definition.schema_version).map(row => row.id));
  return filterNodes(catalog, query, 'ALL').filter(({ entry }) => allowed.has(entry.id) && roleAllows(entry, role));
}

export function addNodeMenuEntries(catalog: StudioGraphCatalog | undefined): CanvasCatalogEntry[] {
  return catalog ? nodeSearchIndex(catalog) : [];
}

export function graphDisplayExecCounts(
  nodes: readonly { definition_id: string }[],
  definitions: readonly { id: string; executable?: boolean }[],
  renderedCount: number,
): { display: number; frame: number; executable: number } {
  const execIds = new Set(definitions.filter(row => row.executable === true).map(row => row.id));
  return {
    display: nodes.length,
    frame: Math.max(0, Math.min(renderedCount, nodes.length)),
    executable: nodes.filter(node => execIds.has(node.definition_id)).length,
  };
}
