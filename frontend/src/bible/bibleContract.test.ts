/**
 * Round2-B 严格解码器测试。
 *
 * 解码器不只是"能解出来"，它是本轮真实性规则的**执行点**：
 *  - 未知必须**是** `UNKNOWN`，不能是一个空白字符串；
 *  - 已 authoring 的值不得为空，`authored` 必须与 `state` 自洽；
 *  - 未解析引用清单必须与引用结论自洽，没提供索引时不允许出现 RESOLVED；
 *  - 后端多一个少一个键、必填表漂移、维度顺序变化，都必须明确失败。
 */

import { describe, expect, it } from 'vitest';

import { ApiError } from '../api';
import { bibleProjection, draftFields, unknownFields } from './bibleContract';
import { fixtureBareProjection, fixtureEmptyProjection, fixtureProjection } from './bibleFixtures.testFixture';
import { CHARACTER_BIBLE_FIELDS, SCENE_BIBLE_FIELDS, UNKNOWN, canonState } from './bibleTypes';
import type { BibleDimension, BibleProjection } from './bibleTypes';

const decode = (value: unknown, id = 'project-1') => bibleProjection(value, id);

function withCharacterDimension(index: number, patch: Partial<BibleDimension>): BibleProjection {
  const projection = fixtureProjection();
  const dimensions = projection.character_bible.entries[0].dimensions.map((item, i) =>
    i === index ? { ...item, ...patch } : item);
  return {
    ...projection,
    character_bible: {
      ...projection.character_bible,
      entries: [{ ...projection.character_bible.entries[0], dimensions }],
    },
  };
}

describe('角色与场景圣经解码器', () => {
  it('解码一份合法 projection', () => {
    const projection = decode(fixtureProjection());
    expect(projection.contract).toBe('studio-bible/1');
    expect(projection.advisory_only).toBe(true);
    expect(projection.execution_authority).toBe(false);
    expect(projection.auto_modify).toBe(false);
    expect(projection.unknown_is_explicit).toBe(true);
    expect(projection.character_bible.entries).toHaveLength(1);
    expect(projection.scene_bible.entries).toHaveLength(1);
  });

  it('身份不符判为 scope mismatch', () => {
    try {
      decode(fixtureProjection(), 'other-project');
      throw new Error('应当抛错');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).problem.code).toBe('STUDIO_BIBLE_SCOPE_MISMATCH');
    }
  });

  it('拒绝未知键与错误的契约/权限位', () => {
    expect(() => decode({ ...fixtureProjection(), extra: 1 })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), contract: 'studio-bible/2' })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), schema_version: 2 })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), advisory_only: false })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), execution_authority: true })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), auto_modify: true })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), unknown_is_explicit: false })).toThrow(ApiError);
  });

  it('拒绝漂移的必填维度表（角色与场景）', () => {
    const missingCharacter = fixtureProjection();
    missingCharacter.required_character_fields = CHARACTER_BIBLE_FIELDS.filter(f => f !== 'reference') as never;
    expect(() => decode(missingCharacter)).toThrow(ApiError);

    const missingScene = fixtureProjection();
    missingScene.required_scene_fields = SCENE_BIBLE_FIELDS.filter(f => f !== 'weather') as never;
    expect(() => decode(missingScene)).toThrow(ApiError);

    const reordered = fixtureProjection();
    reordered.required_scene_fields = [...SCENE_BIBLE_FIELDS].reverse() as never;
    expect(() => decode(reordered)).toThrow(ApiError);

    const nested = fixtureProjection();
    nested.character_bible.required_fields = CHARACTER_BIBLE_FIELDS.filter(f => f !== 'identity') as never;
    expect(() => decode(nested)).toThrow(ApiError);
  });

  it('拒绝维度顺序或数量漂移', () => {
    const projection = fixtureProjection();
    const dimensions = projection.character_bible.entries[0].dimensions;
    projection.character_bible.entries = [{
      ...projection.character_bible.entries[0],
      dimensions: [dimensions[1], dimensions[0], ...dimensions.slice(2)],
    }];
    expect(() => decode(projection)).toThrow(ApiError);
  });

  it('拒绝维度上的未知键', () => {
    expect(() => decode(withCharacterDimension(0, { surprise: true } as never))).toThrow(ApiError);
  });

  it('未知必须就是字面量 UNKNOWN，不能是空白', () => {
    // 这是本轮最重要的一条：把"未知"渲染成空白会被读成"没什么可说的"。
    expect(() => decode(withCharacterDimension(0, { value: '', authored: false, state: 'UNKNOWN' })))
      .toThrow(ApiError);
    expect(() => decode(withCharacterDimension(0, { value: '   ', authored: false, state: 'UNKNOWN' })))
      .toThrow(ApiError);
    // 但字面量 UNKNOWN 必须被接受。
    const accepted = decode(withCharacterDimension(0, { value: UNKNOWN, authored: false, state: 'UNKNOWN' }));
    expect(accepted.character_bible.entries[0].dimensions[0].value).toBe(UNKNOWN);
  });

  it('已 authoring 的值不得为空，且 authored 必须与 state 自洽', () => {
    expect(() => decode(withCharacterDimension(0, { value: '', authored: true, state: 'AUTHORED' })))
      .toThrow(ApiError);
    expect(() => decode(withCharacterDimension(0, { value: '有值', authored: false, state: 'AUTHORED' })))
      .toThrow(ApiError);
    expect(() => decode(withCharacterDimension(0, { value: UNKNOWN, authored: true, state: UNKNOWN as never })))
      .toThrow(ApiError);
    expect(() => decode(withCharacterDimension(0, { state: 'MAYBE' } as never))).toThrow(ApiError);
  });

  it('未解析引用清单必须与引用结论自洽', () => {
    expect(() => decode(withCharacterDimension(3, { unresolved_references: ['a1'] }))).toThrow(ApiError);
    expect(() => decode(withCharacterDimension(3, { unresolved_references: [] }))).toThrow(ApiError);
    expect(() => decode(withCharacterDimension(3, {
      references: [{ asset_id: 'a1', resolution: 'RESOLVED' }, { asset_id: 'a2', resolution: 'RESOLVED' }],
      unresolved_references: ['a2'],
    }))).toThrow(ApiError);
  });

  it('没有索引时不允许出现任何 RESOLVED 引用', () => {
    expect(() => decode(withCharacterDimension(3, { verification: 'NO_INDEX_SUPPLIED' }))).toThrow(ApiError);
    // 全部未解析时，NO_INDEX_SUPPLIED 是自洽的。
    const consistent = decode(withCharacterDimension(3, {
      references: [{ asset_id: 'a1', resolution: 'UNRESOLVED' }, { asset_id: 'a2', resolution: 'UNRESOLVED' }],
      unresolved_references: ['a1', 'a2'], verification: 'NO_INDEX_SUPPLIED',
    }));
    expect(consistent.character_bible.entries[0].dimensions[3].verification).toBe('NO_INDEX_SUPPLIED');
  });

  it('拒绝计数与条目数不一致', () => {
    const projection = fixtureProjection();
    projection.character_bible.character_count = 5;
    expect(() => decode(projection)).toThrow(ApiError);
    const other = fixtureProjection();
    other.scene_bible.location_count = 3;
    expect(() => decode(other)).toThrow(ApiError);
  });

  it('拒绝把未 authoring 的维度算错成 gap，或 gap 里出现未知字段', () => {
    const projection = fixtureProjection();
    projection.gaps = { characters: [], scenes: [{ location_id: 'l1', field: 'not_a_dimension' }] };
    expect(() => decode(projection)).toThrow(ApiError);
  });

  it('接受空项目（没有角色也没有地点）', () => {
    const projection = decode(fixtureEmptyProjection());
    expect(projection.character_bible.entries).toHaveLength(0);
    expect(projection.scene_bible.entries).toHaveLength(0);
  });

  it('接受一个完全没有外形的角色', () => {
    const projection = decode(fixtureBareProjection());
    const dimensions = projection.character_bible.entries[0].dimensions;
    const appearance = dimensions.find(item => item.field === 'appearance')!;
    expect(appearance.state).toBe('UNKNOWN');
    expect(appearance.value).toBe(UNKNOWN);
    expect(appearance.authored).toBe(false);
  });

  it('拒绝超界的项目标识', () => {
    expect(() => decode(fixtureProjection(), 'x'.repeat(241))).toThrow(ApiError);
    expect(() => decode(fixtureProjection(), '  ')).toThrow(ApiError);
  });
});

describe('界面派生', () => {
  it('canon 判定区分 CANON / DRAFT / 不适用', () => {
    const projection = decode(fixtureProjection());
    const appearance = projection.character_bible.entries[0].dimensions.find(d => d.field === 'appearance')!;
    const architecture = projection.scene_bible.entries[0].dimensions.find(d => d.field === 'architecture')!;
    const material = projection.scene_bible.entries[0].dimensions.find(d => d.field === 'material')!;
    const identity = projection.character_bible.entries[0].dimensions.find(d => d.field === 'identity')!;
    expect(canonState(appearance)).toBe('CANON');
    expect(canonState(architecture)).toBe('DRAFT');
    expect(canonState(material)).toBe('NOT_APPLICABLE');
    // 非世界记录的维度没有 record_status，因此按 canon 呈现（它是原 owner 的事实）。
    expect(canonState(identity)).toBe('CANON');
  });

  it('未 authoring 与 DRAFT 的字段清单', () => {
    const scene = decode(fixtureProjection()).scene_bible.entries[0];
    expect(unknownFields(scene)).toEqual(['material', 'weather']);
    expect(draftFields(scene)).toEqual(['architecture', 'lighting', 'time', 'mood']);
  });
});
