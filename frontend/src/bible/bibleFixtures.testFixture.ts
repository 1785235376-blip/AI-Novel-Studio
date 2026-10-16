/**
 * Round2-B 测试夹具：形状与后端返**完全一致**的 projection。
 *
 * 夹具刻意同时包含四种状态，这样真实性规则在测试里能被真正核对，而不是只靠一个漂亮样本：
 *  - `UNKNOWN`（场景 material / weather —— 有 DRAFT 记录但该字段没填）
 *  - `DRAFT`（整个场景视觉记录未批准，已填的字段仍会显示但标注非 canon）
 *  - `CANON · APPROVED`（角色外形记录已批准）
 *  - `RESOLVED` / `UNRESOLVED`（参考素材 a1 在索引里，a2 不在）
 */

import type {
  BibleDimension, BibleProjection, CharacterBibleEntry, SceneBibleEntry,
} from './bibleTypes';
import { UNKNOWN } from './bibleTypes';

function base(field: string, label: string, source: string, value: string): BibleDimension {
  return { field, label, source, value, authored: true, state: 'AUTHORED' };
}

function unknownDimension(field: string, label: string, source: string, recordStatus: string | null): BibleDimension {
  return {
    field, label, source, value: UNKNOWN, authored: false, state: 'UNKNOWN',
    authoritative: false, record_status: recordStatus,
  };
}

const CHARACTER_DIMENSIONS: BibleDimension[] = [
  base('identity', '身份', 'characters.name/age/role', '林向晚, 29, 主角, ALIVE'),
  { ...base('appearance', '外形', 'world_records.CHARACTER_VISUAL.appearance', '瘦高，短发'),
    authoritative: true, record_status: 'APPROVED' },
  { ...base('clothing', '服装', 'world_records.CHARACTER_VISUAL.clothing', '深色风衣'),
    authoritative: true, record_status: 'APPROVED' },
  {
    field: 'reference', label: '参考图', source: 'world_records.CHARACTER_VISUAL.reference_asset_ids',
    value: 'a1, a2', authored: true, state: 'AUTHORED',
    references: [{ asset_id: 'a1', resolution: 'RESOLVED' }, { asset_id: 'a2', resolution: 'UNRESOLVED' }],
    unresolved_references: ['a2'], verification: 'INDEX_SUPPLIED',
  },
  base('behavior', '行为', 'world_records.PSYCHOLOGY.state/motivation', '克制, 查明真相'),
  {
    ...base('relationship', '关系', 'world_records.RELATIONSHIP.state', '旧识'),
    relationships: [{ target_character_id: 'c2', state: '旧识', authoritative: true }],
  },
];

const SCENE_DIMENSIONS: BibleDimension[] = [
  { ...base('location', '地点', 'locations.name', '旧城公寓, l1'), geography_records: 0 },
  { ...base('architecture', '建筑', 'world_records.SCENE_VISUAL.architecture', '老式砖楼'),
    authoritative: false, record_status: 'DRAFT' },
  unknownDimension('material', '材质', 'world_records.SCENE_VISUAL.material', 'DRAFT'),
  { ...base('lighting', '灯光', 'world_records.SCENE_VISUAL.lighting', '暖光'),
    authoritative: false, record_status: 'DRAFT' },
  unknownDimension('weather', '天气', 'world_records.SCENE_VISUAL.weather', 'DRAFT'),
  { ...base('time', '时间', 'world_records.SCENE_VISUAL.time_of_day', '夜'),
    authoritative: false, record_status: 'DRAFT' },
  { ...base('mood', '氛围', 'world_records.SCENE_VISUAL.mood', '压抑'),
    authoritative: false, record_status: 'DRAFT' },
];

export const CHARACTER_ENTRY: CharacterBibleEntry = {
  character_id: 'c1',
  name: '林向晚',
  dimensions: CHARACTER_DIMENSIONS,
  used_in: [
    { document_id: 'd1', mode: 'STORYBOARD', role: 'SCENE_CAST', scene_id: 's1' },
    { document_id: 'd1', mode: 'STORYBOARD', role: 'SHOT_CAST', shot_id: 'sh1' },
  ],
  visual_record_status: 'APPROVED',
  visual_authoritative: true,
};

export const SCENE_ENTRY: SceneBibleEntry = {
  location_id: 'l1',
  name: '旧城公寓',
  dimensions: SCENE_DIMENSIONS,
  reference_asset_ids: [],
  used_in: [{ document_id: 'd1', mode: 'STORYBOARD', role: 'SCENE_LOCATION', scene_id: 's1' }],
  visual_record_status: 'DRAFT',
  visual_authoritative: false,
};

export function fixtureProjection(overrides: Partial<BibleProjection> = {}): BibleProjection {
  const baseProjection: BibleProjection = {
    contract: 'studio-bible/1',
    schema_version: 1,
    advisory_only: true,
    execution_authority: false,
    auto_modify: false,
    unknown_is_explicit: true,
    required_character_fields: ['identity', 'appearance', 'clothing', 'reference', 'behavior', 'relationship'],
    required_scene_fields: ['location', 'architecture', 'material', 'lighting', 'weather', 'time', 'mood'],
    character_bible: {
      contract: 'studio-character-bible/1',
      schema_version: 1,
      required_fields: ['identity', 'appearance', 'clothing', 'reference', 'behavior', 'relationship'],
      entries: [CHARACTER_ENTRY],
      character_count: 1,
    },
    scene_bible: {
      contract: 'studio-scene-bible/1',
      schema_version: 1,
      required_fields: ['location', 'architecture', 'material', 'lighting', 'weather', 'time', 'mood'],
      entries: [SCENE_ENTRY],
      location_count: 1,
    },
    gaps: {
      characters: [],
      scenes: [{ location_id: 'l1', field: 'material' }, { location_id: 'l1', field: 'weather' }],
    },
    project_id: 'project-1',
    scope: { mode: 'local', novel_id: 'project-1' },
    generated_at: '2026-10-15T00:00:00+00:00',
    project_context: { title: '旧城回声', genre: '悬疑科幻', inherited_not_authored: true },
    visual_owner: 'WorldService records (CHARACTER_VISUAL / SCENE_VISUAL)',
    world_owner_available: true,
  };
  return { ...baseProjection, ...overrides };
}

/** 一个还没 authoring 任何外形的角色：外形/服装/参考图都必须是 UNKNOWN。 */
export function fixtureBareProjection(): BibleProjection {
  const projection = fixtureProjection();
  const bare: CharacterBibleEntry = {
    character_id: 'c9',
    name: '未作者化角色',
    dimensions: CHARACTER_DIMENSIONS.map(dimension =>
      dimension.field === 'identity'
        ? { ...dimension, value: '未作者化角色', source: 'characters.name/age/role' }
        : {
            field: dimension.field, label: dimension.label, source: dimension.source,
            value: UNKNOWN, authored: false, state: 'UNKNOWN',
            ...(dimension.references ? { references: [], unresolved_references: [], verification: 'NO_INDEX_SUPPLIED' } : {}),
            ...(dimension.authoritative !== undefined ? { authoritative: false, record_status: null } : {}),
            ...(dimension.relationships ? { relationships: [] } : {}),
          }),
    used_in: [],
    visual_record_status: null,
    visual_authoritative: false,
  };
  return {
    ...projection,
    character_bible: { ...projection.character_bible, entries: [bare], character_count: 1 },
    scene_bible: { ...projection.scene_bible, entries: [], location_count: 0 },
    gaps: { characters: [], scenes: [] },
  };
}

/** 一个既没有角色也没有地点的项目。 */
export function fixtureEmptyProjection(): BibleProjection {
  const projection = fixtureProjection();
  return {
    ...projection,
    character_bible: { ...projection.character_bible, entries: [], character_count: 0 },
    scene_bible: { ...projection.scene_bible, entries: [], location_count: 0 },
    gaps: { characters: [], scenes: [] },
  };
}
