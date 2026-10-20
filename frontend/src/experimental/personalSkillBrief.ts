import type {GraphBriefSource} from './reviewedGraphBrief';
import type { TemplatePackage } from './templateLibraryClient';

export const briefFields = [
  ['purpose', '用途'], ['writing_goals', '写作目标'], ['constraints', '约束'], ['checklist', '检查清单'],
] as const;
export type BriefText = Record<(typeof briefFields)[number][0], string>;
export type BriefIdentity = { id: string; title: string; version: string; author: string; license: string };
export type PresetSource = { pluginId: string; resourceId: string; sha256: string };
export const emptyBrief = (): BriefText => ({ purpose: '', writing_goals: '', constraints: '', checklist: '' });
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value)).length;
const fail = (): never => { throw new Error('预设格式不受支持；需要 schema 1.0 的声明式写作预设及用途、目标、约束、检查清单。'); };
const bounded = (value: unknown, max: number): value is string => typeof value === 'string' && value.length <= max;

/** Pure text projection. Metadata and parameter hints are never executable controls. */
export function projectWritingPreset(value: unknown, selected: PresetSource): { text: BriefText; source: PresetSource; omitted: string[] } {
  if (!object(value) || bytes(value) > 128000 || value.validated !== true || value.execution_supported !== false ||
    value.kind !== 'writing_presets' || value.plugin_id !== selected.pluginId || value.resource_id !== selected.resourceId ||
    value.sha256 !== selected.sha256 || !/^[a-f0-9]{64}$/.test(selected.sha256) || !object(value.data)) fail();
  const data = (value as Record<string, unknown>).data as Record<string, unknown>;
  if (data.schema_version !== '1.0' || data.content_class !== 'declarative_data' || data.execution_supported !== false ||
    data.execution !== 'not_supported' || data.host_application !== 'not_implemented') fail();
  const text = emptyBrief();
  if (!bounded(data.purpose, 8000)) fail();
  text.purpose = data.purpose as string;
  for (const field of ['writing_goals', 'constraints', 'checklist'] as const) {
    const list = data[field];
    if (!Array.isArray(list) || list.length > 100 || !list.every(item => bounded(item, 8000))) fail();
    text[field] = (list as string[]).join('\n');
    if (text[field].length > 8000) fail();
  }
  return { text, source: { pluginId: selected.pluginId, resourceId: selected.resourceId, sha256: selected.sha256 }, omitted: Object.keys(data).filter(key => !briefFields.some(([field]) => field === key)) };
}

export function personalBriefPackage(identity: BriefIdentity, text: BriefText, source?: PresetSource, unverifiedModelCandidate=false, graphSource?:GraphBriefSource): TemplatePackage {
  if (!/^personal-[a-z0-9][a-z0-9-]{0,70}$/.test(identity.id)) throw new Error('个人标识需以 personal- 开头，只含小写字母、数字与连字符，总长不超过 80。');
  if (!/^\d{1,4}\.\d{1,4}\.\d{1,4}$/.test(identity.version)) throw new Error('版本需为三个数字段，例如 1.0.0；修改已有内容需使用新版本。');
  for (const field of ['title', 'author', 'license'] as const) {
    if (!identity[field].trim() || identity[field].length > 160) throw new Error('请填写标题、作者与许可声明，每项最多 160 字。');
  }
  if (briefFields.some(([key]) => !bounded(text[key], 8000)) || !briefFields.some(([key]) => text[key].trim())) throw new Error('请填写至少一项简报内容，每项最多 8000 字。');
  const provenance = graphSource ? JSON.stringify(graphSource) : unverifiedModelCandidate ? 'PERSONAL_USER_SUPPLIED_MODEL_CANDIDATE_UNVERIFIED' : source ? JSON.stringify({ kind: 'PERSONAL_TEXT_PROJECTION', ...source, publisher_verified: false }) : 'PERSONAL_SELF_WRITTEN_DECLARATION';
  if (provenance.length > 1000) throw new Error('来源标识过长，无法保存。');
  const result: TemplatePackage = {
    schema_version: 1,
    manifest: { ...identity, type: 'review', description: '个人写作简报：仅供人工查看、编辑与复用，不执行预设。', dependencies: [], provenance,
      compatibility: { protocol: 'LOCAL_BOUNDED_JSON_V1', schema_versions: [1], import_mode: 'READ_ONLY_DECLARATION' },
      permissions: { execute: false, network: false, manuscript_write: false, grant_capabilities: false, executable_plugins: 'DENY_ALL' } },
    content: { sections: briefFields.map(([key, title]) => ({ key, title, text: text[key] })) },
  };
  if (bytes(result) > 128000) throw new Error('简报超过 128000 字节，请缩短内容。');
  return result;
}
