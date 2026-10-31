/**
 * Phase14-A 测试夹具：一份形状与后端 `studio-director-workspace/1` 完全一致的投影。
 *
 * 夹具刻意包含一个**旧写法**景别（`很宽的镜头`）和一个文档级 authoring 的题材，
 * 这样"旧写法原样保留"与"authoring ≠ 测量"两条规则在测试里都能被真正核对，
 * 而不是只靠一个全规范值的漂亮样本。
 */

import type {
  CameraLanguageUsage, DirectorIntentRecord, DirectorWorkspaceProjection, ShotCardProjection,
} from './directorWorkspaceTypes';

//: 七个必填意图维度的夹具，顺序与 `DIRECTOR_INTENT_FIELDS` 一致。
//: 用函数构造，避免在 `CAMERA_USAGE` 初始化前读取它。
function intentFields(): DirectorIntentRecord[] {
  return [
  { field: 'visual_goal', label: '视觉目标', kind: 'DOCUMENT_AUTHORED', authored_scope: 'DOCUMENT', value: '冷峻写实', authored: true, source: 'visual_target.style', owner: 'DirectorVisualTarget.style', usage: null, detail: { rhythm: '缓—急—缓', reference_works: ['《银翼杀手》'] } },
  { field: 'mood', label: '情绪基调', kind: 'DOCUMENT_AUTHORED', authored_scope: 'DOCUMENT', value: '压抑', authored: true, source: 'visual_target.atmosphere', owner: 'DirectorVisualTarget.atmosphere', usage: null },
  { field: 'genre', label: '题材', kind: 'DOCUMENT_AUTHORED', authored_scope: 'DOCUMENT', value: '悬疑科幻', authored: true, source: 'visual_target.genre', owner: 'DirectorVisualTarget.genre', usage: null },
  { field: 'camera_language', label: '镜头语言', kind: 'PER_SHOT_MEASURED', authored_scope: 'PER_SHOT', value: '', authored: false, source: 'shot_size/camera_motion/lens/composition', owner: 'ShotCard / DirectorNote', usage: CAMERA_USAGE },
  { field: 'lighting', label: '灯光', kind: 'PER_SHOT_MEASURED', authored_scope: 'PER_SHOT', value: '', authored: false, source: 'lighting', owner: 'ShotCard.lighting / DirectorNote.lighting', usage: { measured_over_rows: 2, authored_rows: 2, unauthored_rows: 0, dimensions: { lighting: { rows: 2, authored_rows: 2, values: [{ value: '暖光', count: 1 }, { value: '冷光', count: 1 }] } } } },
  { field: 'color_direction', label: '色彩方向', kind: 'DOCUMENT_AUTHORED', authored_scope: 'DOCUMENT', value: '青蓝低饱和', authored: true, source: 'visual_target.color', owner: 'DirectorVisualTarget.color', usage: null },
  { field: 'performance_direction', label: '表演方向', kind: 'PER_SHOT_MEASURED', authored_scope: 'PER_SHOT', value: '', authored: false, source: 'performance/blocking/character_state/emotion', owner: 'ShotCard / DirectorNote', usage: { measured_over_rows: 2, authored_rows: 1, unauthored_rows: 1, dimensions: { emotion: { rows: 2, authored_rows: 2, values: [{ value: '迟疑', count: 1 }, { value: '警觉', count: 1 }] }, performance: { rows: 2, authored_rows: 1, values: [{ value: '克制', count: 1 }] } } } },
  ];
}

const VOCABULARY: CameraLanguageUsage['vocabulary'] = {
  shot_size: {
    members: ['EXTREME_WIDE', 'WIDE', 'MEDIUM', 'CLOSE_UP', 'EXTREME_CLOSE_UP'],
    aliases: { 'CLOSE UP': 'CLOSE_UP', EWS: 'EXTREME_WIDE' },
    alias_keys_are_folded: true,
  },
  camera_motion: {
    members: ['STATIC', 'PAN', 'TILT', 'DOLLY', 'TRACKING', 'CRANE', 'HANDHELD'],
    aliases: { 'DOLLY IN': 'DOLLY' }, alias_keys_are_folded: true,
  },
  lens: { members: ['WIDE', 'NORMAL', 'TELEPHOTO', 'MACRO'], aliases: {}, alias_keys_are_folded: true },
  composition: {
    members: ['RULE_OF_THIRDS', 'CENTER', 'SYMMETRY', 'LEADING_LINES'],
    aliases: { 'RULE OF THIRDS': 'RULE_OF_THIRDS' }, alias_keys_are_folded: true,
  },
};

export const CAMERA_USAGE: CameraLanguageUsage = {
  measured_over_rows: 2,
  dimensions: {
    shot_size: {
      rows: 2, authored_rows: 2,
      values: [{ value: 'WIDE', code: 'CANONICAL', count: 1 },
               { value: '很宽的镜头', code: 'LEGACY_PASSTHROUGH', count: 1 }],
    },
    camera_motion: { rows: 2, authored_rows: 2, values: [{ value: 'STATIC', code: 'CANONICAL', count: 1 }, { value: 'DOLLY', code: 'CANONICAL', count: 1 }] },
    lens: { rows: 2, authored_rows: 2, values: [{ value: 'NORMAL', code: 'CANONICAL', count: 1 }, { value: 'TELEPHOTO', code: 'CANONICAL', count: 1 }] },
    composition: { rows: 2, authored_rows: 2, values: [{ value: 'CENTER', code: 'CANONICAL', count: 1 }, { value: 'RULE_OF_THIRDS', code: 'CANONICAL', count: 1 }] },
  },
  authored_values: 8, canonical_values: 7,
  legacy_values_preserved: ['很宽的镜头'],
  canonical_ratio: 0.875,
  vocabulary: VOCABULARY,
};

export function fixtureShotCard(overrides: Partial<ShotCardProjection> = {}): ShotCardProjection {
  return {
    contract: 'studio-shot-card/1',
    shot_id: 'shot-01', number: 1, scene_id: 'scene-1',
    duration: { seconds: 6, authored: true },
    camera: { shot_size: 'WIDE', camera_motion: 'STATIC', lens: 'NORMAL', composition: 'CENTER', angle: 'EYE_LEVEL' },
    camera_classification: { shot_size: 'CANONICAL', camera_motion: 'CANONICAL', lens: 'CANONICAL', composition: 'CANONICAL' },
    camera_canonical_ratio: 1,
    lens: { field: 'lens', value: 'NORMAL', authored: true, source: 'ShotCard.lens', owner: 'ShotCard.lens', code: 'CANONICAL' },
    movement: { field: 'movement', value: 'STATIC', authored: true, source: 'ShotCard.camera_motion', owner: 'ShotCard.camera_motion', code: 'CANONICAL' },
    composition: { field: 'composition', value: 'CENTER', authored: true, source: 'ShotCard.composition', owner: 'ShotCard.composition', code: 'CANONICAL' },
    lighting: { field: 'lighting', value: '暖光', authored: true, source: 'ShotCard.lighting', owner: 'ShotCard.lighting' },
    character: { field: 'character', values: ['林向晚'], authored: true, source: 'ShotCard.characters', owner: 'ShotCard.characters' },
    action: { field: 'action', value: '推门', authored: true, source: 'ShotCard.action', owner: 'ShotCard.action' },
    emotion: { field: 'emotion', value: '迟疑', authored: true, source: 'ShotCard.emotion', owner: 'ShotCard.emotion' },
    audio: {
      field: 'audio', sound: '雨声', sound_effect: '门轴',
      dialogue: [{ speaker: '林向晚', text: '有人吗', delivery: '' }],
      authored: true, source: 'ShotCard.sound/sound_effect/dialogue', owner: 'ShotCard',
    },
    director_note_ids: ['note-1'],
    ...overrides,
  };
}

export function fixtureProjection(overrides: Partial<DirectorWorkspaceProjection> = {}): DirectorWorkspaceProjection {
  const base: DirectorWorkspaceProjection = {
    contract: 'studio-director-workspace/1',
    schema_version: 1,
    advisory_only: true,
    execution_authority: false,
    auto_modify: false,
    project_id: 'project-1',
    scope: { mode: 'local', novel_id: 'project-1' },
    generated_at: '2026-10-15T00:00:00+00:00',
    project_context: { title: '旧城回声', genre: '悬疑科幻', inherited_not_authored: true },
    document: { id: 'doc-1', version: 3, mode: 'STORYBOARD', title: '旧城回声 分镜', status: 'DRAFT' },
    required_shot_card_fields: [
      'shot_id', 'duration', 'camera', 'lens', 'movement', 'composition',
      'lighting', 'character', 'action', 'emotion', 'audio',
    ],
    director_intent: {
      contract: 'studio-director-intent/1',
      schema_version: 1,
      advisory_only: true,
      auto_modify: false,
      measured_over: 'SHOTS',
      required_fields: [
        'visual_goal', 'mood', 'genre', 'camera_language', 'lighting', 'color_direction', 'performance_direction',
      ],
      fields: intentFields(),
      dimensions: Object.fromEntries(intentFields().map(field => [field.field, field])) as
        DirectorWorkspaceProjection['director_intent']['dimensions'],
    },
    shot_cards: [
      fixtureShotCard(),
      fixtureShotCard({
        shot_id: 'shot-02', number: 2, scene_id: 'scene-2',
        duration: { seconds: 4, authored: true },
        camera: { shot_size: '很宽的镜头', camera_motion: 'DOLLY', lens: 'TELEPHOTO', composition: 'RULE_OF_THIRDS', angle: 'LOW' },
        camera_classification: { shot_size: 'LEGACY_PASSTHROUGH', camera_motion: 'CANONICAL', lens: 'CANONICAL', composition: 'CANONICAL' },
        camera_canonical_ratio: 0.75,
        movement: { field: 'movement', value: 'DOLLY', authored: true, source: 'ShotCard.camera_motion', owner: 'ShotCard.camera_motion', code: 'CANONICAL' },
        lens: { field: 'lens', value: 'TELEPHOTO', authored: true, source: 'ShotCard.lens', owner: 'ShotCard.lens', code: 'CANONICAL' },
        composition: { field: 'composition', value: 'RULE_OF_THIRDS', authored: true, source: 'ShotCard.composition', owner: 'ShotCard.composition', code: 'CANONICAL' },
        lighting: { field: 'lighting', value: '冷光', authored: true, source: 'ShotCard.lighting', owner: 'ShotCard.lighting' },
        action: { field: 'action', value: '回头', authored: true, source: 'ShotCard.action', owner: 'ShotCard.action' },
        emotion: { field: 'emotion', value: '警觉', authored: true, source: 'ShotCard.emotion', owner: 'ShotCard.emotion' },
        audio: { field: 'audio', sound: '', sound_effect: '风声', dialogue: [], authored: true, source: 'ShotCard.sound/sound_effect/dialogue', owner: 'ShotCard' },
        director_note_ids: [],
      }),
    ],
    continuity: {
      contract: 'studio-continuity-panel/1',
      schema_version: 1,
      warning_only: true,
      auto_modify: false,
      required_dimensions: ['characters', 'outfit', 'environment', 'time', 'lighting'],
      dimensions: [
        { field: 'characters', label: '角色', code: 'CONTINUITY_CHARACTERS_CHANGED', sources: ['continuity.characters', 'shot.characters'], compared_pairs: 1, unknown_pairs: 0 },
        { field: 'outfit', label: '服装', code: 'CONTINUITY_OUTFIT_CHANGED', sources: ['continuity.outfit'], compared_pairs: 1, unknown_pairs: 0 },
        { field: 'environment', label: '场景', code: 'CONTINUITY_ENVIRONMENT_CHANGED', sources: ['continuity.environment', 'shot.environment'], compared_pairs: 1, unknown_pairs: 0 },
        { field: 'time', label: '时间', code: 'CONTINUITY_TIME_CHANGED', sources: ['continuity.time'], compared_pairs: 1, unknown_pairs: 0 },
        { field: 'lighting', label: '灯光', code: 'CONTINUITY_LIGHTING_CHANGED', sources: ['continuity.lighting', 'shot.lighting'], compared_pairs: 1, unknown_pairs: 0 },
      ],
      excluded: [{ field: 'camera', reason: 'CAMERA_MOVE_IS_DIRECTION' }],
      shot_count: 2, compared_pairs: 1,
      warnings: [
        { code: 'CONTINUITY_OUTFIT_CHANGED', field: 'outfit', label: '服装', severity: 'WARNING', previous_shot_id: 'shot-01', next_shot_id: 'shot-02', previous: '红色外套', next: '蓝色外套' },
        { code: 'CONTINUITY_LIGHTING_CHANGED', field: 'lighting', label: '灯光', severity: 'WARNING', previous_shot_id: 'shot-01', next_shot_id: 'shot-02', previous: '暖光', next: '冷光' },
      ],
    },
  };
  return { ...base, ...overrides };
}

/** 一份"什么都没 authoring"的投影：用来核对 EMPTY 状态。 */
export function fixtureEmptyProjection(): DirectorWorkspaceProjection {
  const base = fixtureProjection();
  // 空文档仍然带完整词表：规范取值表是 owner 声明的，不随数据多少而变化。
  const emptyCameraUsage: CameraLanguageUsage = {
    ...CAMERA_USAGE,
    measured_over_rows: 0, authored_values: 0, canonical_values: 0,
    legacy_values_preserved: [], canonical_ratio: 0,
    dimensions: Object.fromEntries(Object.keys(CAMERA_USAGE.dimensions)
      .map(key => [key, { rows: 0, authored_rows: 0, values: [] }])),
  };
  const fields = base.director_intent.fields.map(field => {
    if (field.kind === 'DOCUMENT_AUTHORED') return { ...field, value: '', authored: false };
    if (field.field === 'camera_language') return { ...field, usage: emptyCameraUsage };
    return { ...field, usage: { measured_over_rows: 0, authored_rows: 0, unauthored_rows: 0, dimensions: {} } };
  });
  return {
    ...base,
    shot_cards: [],
    director_intent: {
      ...base.director_intent,
      measured_over: 'NONE',
      fields,
      dimensions: Object.fromEntries(fields.map(field => [field.field, field])) as
        DirectorWorkspaceProjection['director_intent']['dimensions'],
    },
    continuity: {
      ...base.continuity, shot_count: 0, compared_pairs: 0, warnings: [],
      dimensions: base.continuity.dimensions.map(dimension => ({ ...dimension, compared_pairs: 0, unknown_pairs: 0 })),
    },
  };
}
