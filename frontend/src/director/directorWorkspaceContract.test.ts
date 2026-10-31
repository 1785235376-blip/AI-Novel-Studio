/**
 * Phase14-A 严格解码器测试。
 *
 * 解码器不只是"能解出来"，它还要在**契约漂移**时明确失败：后端少报一个必填维度、
 * 把逐镜头统计说成文档级 authoring、或把 warning-only 改成可修改，都必须抛错，
 * 而不是让界面安静地少显示一行或显示错的语义。
 */

import { describe, expect, it } from 'vitest';

import { ApiError } from '../api';
import {
  cameraVocabulary, cameraVocabularyOptions, directorWorkspaceProjection,
} from './directorWorkspaceContract';
import { CAMERA_USAGE, fixtureEmptyProjection, fixtureProjection } from './directorWorkspaceFixtures.testFixture';
import { CONTINUITY_DIMENSIONS, DIRECTOR_INTENT_FIELDS, SHOT_CARD_FIELDS } from './directorWorkspaceTypes';

const decode = (value: unknown, id = 'doc-1') => directorWorkspaceProjection(value, id);

describe('导演工作台解码器', () => {
  it('解码一份合法投影', () => {
    const projection = decode(fixtureProjection());
    expect(projection.contract).toBe('studio-director-workspace/1');
    expect(projection.advisory_only).toBe(true);
    expect(projection.execution_authority).toBe(false);
    expect(projection.auto_modify).toBe(false);
    expect(projection.shot_cards).toHaveLength(2);
    expect(projection.document.version).toBe(3);
  });

  it('把身份不符判为 scope mismatch，而不是通用解析失败', () => {
    try {
      decode(fixtureProjection(), 'other-doc');
      throw new Error('应当抛错');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).problem.code).toBe('STUDIO_DIRECTOR_WORKSPACE_SCOPE_MISMATCH');
    }
  });

  it('拒绝未知键、错误契约与放开的权限位', () => {
    expect(() => decode({ ...fixtureProjection(), extra: 1 })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), contract: 'studio-director-workspace/2' })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), advisory_only: false })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), execution_authority: true })).toThrow(ApiError);
    expect(() => decode({ ...fixtureProjection(), auto_modify: true })).toThrow(ApiError);
  });

  it('拒绝漂移的必填字段表', () => {
    const missingGenre = fixtureProjection();
    missingGenre.director_intent.required_fields = DIRECTOR_INTENT_FIELDS.filter(field => field !== 'genre') as never;
    expect(() => decode(missingGenre)).toThrow(ApiError);

    const reordered = fixtureProjection();
    reordered.director_intent.required_fields = [...DIRECTOR_INTENT_FIELDS].reverse() as never;
    expect(() => decode(reordered)).toThrow(ApiError);

    const missingShotField = fixtureProjection();
    missingShotField.required_shot_card_fields = SHOT_CARD_FIELDS.filter(field => field !== 'emotion') as never;
    expect(() => decode(missingShotField)).toThrow(ApiError);

    const missingDimension = fixtureProjection();
    missingDimension.continuity.required_dimensions = CONTINUITY_DIMENSIONS.filter(field => field !== 'time') as never;
    expect(() => decode(missingDimension)).toThrow(ApiError);
  });

  it('拒绝把逐镜头统计冒充成文档级 authoring', () => {
    const confused = fixtureProjection();
    confused.director_intent.fields = confused.director_intent.fields.map(field =>
      field.field === 'camera_language' ? { ...field, authored_scope: 'DOCUMENT' as const } : field);
    expect(() => decode(confused)).toThrow(ApiError);
  });

  it('拒绝一个可以自动修改的连续性面板', () => {
    const writable = fixtureProjection();
    (writable.continuity as { auto_modify: boolean }).auto_modify = true;
    expect(() => decode(writable)).toThrow(ApiError);
    const notWarningOnly = fixtureProjection();
    (notWarningOnly.continuity as { warning_only: boolean }).warning_only = false;
    expect(() => decode(notWarningOnly)).toThrow(ApiError);
  });

  it('拒绝被算错的覆盖度（比较对数与镜头数不一致）', () => {
    const broken = fixtureProjection();
    broken.continuity.compared_pairs = 5;
    expect(() => decode(broken)).toThrow(ApiError);
  });

  it('拒绝被算错的统计行数（已填写 + 未填写 ≠ 总数）', () => {
    const broken = fixtureProjection();
    const lighting = broken.director_intent.fields.find(field => field.field === 'lighting');
    (lighting!.usage as { authored_rows: number }).authored_rows = 99;
    expect(() => decode(broken)).toThrow(ApiError);
  });

  it('拒绝一个不是提示级别的连续性告警', () => {
    const error = fixtureProjection();
    (error.continuity.warnings[0] as { severity: string }).severity = 'ERROR';
    expect(() => decode(error)).toThrow(ApiError);
  });

  it('接受一份真实形态的空文档（没有镜头、什么都没 authoring）', () => {
    const projection = decode(fixtureEmptyProjection());
    expect(projection.shot_cards).toHaveLength(0);
    expect(projection.continuity.warnings).toHaveLength(0);
    expect(projection.continuity.compared_pairs).toBe(0);
    expect(projection.director_intent.measured_over).toBe('NONE');
  });

  it('拒绝超界的文档标识，而不是发一个注定失败的请求', () => {
    expect(() => decode(fixtureProjection(), 'x'.repeat(241))).toThrow(ApiError);
    expect(() => decode(fixtureProjection(), '   ')).toThrow(ApiError);
  });
});

describe('镜头语言词表绑定', () => {
  it('词表只来自后端投影，前端不写死', () => {
    const vocabulary = cameraVocabulary(fixtureProjection().director_intent);
    expect(vocabulary.shot_size.members).toEqual(CAMERA_USAGE.vocabulary.shot_size.members);
    expect(vocabulary.camera_motion.members).toContain('DOLLY');
    expect(vocabulary.shot_size.alias_keys_are_folded).toBe(true);
  });

  it('词表不随数据多少变化：空文档仍然发布完整规范取值表', () => {
    const vocabulary = cameraVocabulary(fixtureEmptyProjection().director_intent);
    expect(vocabulary.shot_size.members).toEqual(CAMERA_USAGE.vocabulary.shot_size.members);
    expect(vocabulary.camera_motion.members).toContain('TRACKING');
  });

  it('没有镜头语言维度时返回空表，绝不回退到本地硬编码词表', () => {
    const intent = { dimensions: { camera_language: { usage: null } } };
    expect(cameraVocabulary(intent as never)).toEqual({});
  });

  it('摊平成下拉选项', () => {
    const options = cameraVocabularyOptions(cameraVocabulary(fixtureProjection().director_intent));
    expect(options.map(option => option.field)).toEqual(
      Object.keys(CAMERA_USAGE.vocabulary));
    expect(options.find(option => option.field === 'composition')?.aliases['RULE OF THIRDS']).toBe('RULE_OF_THIRDS');
  });
});
