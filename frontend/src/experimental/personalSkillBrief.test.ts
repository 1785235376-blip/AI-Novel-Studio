import { expect, it } from 'vitest';
import { emptyBrief, personalBriefPackage, projectWritingPreset } from './personalSkillBrief';
const source = { pluginId: 'novel-craft-pack', resourceId: 'resources:scene.json', sha256: 'a'.repeat(64) };
const data = { schema_version: '1.0', content_class: 'declarative_data', execution_supported: false, execution: 'not_supported', host_application: 'not_implemented', purpose: '目的', writing_goals: ['目标一', '目标二'], constraints: ['约束'], checklist: ['核对'], parameter_hints: { ignored: true } };
const detail = { plugin_id: source.pluginId, resource_id: source.resourceId, sha256: source.sha256, kind: 'writing_presets', validated: true, execution_supported: false, data };
const identity = { id: 'personal-scene', title: '我的场景简报', version: '1.0.0', author: '我', license: '仅供本人使用；来源许可待核对' };
it('projects four text fields, records omissions and exact source without mutating the original', () => {
  const before = JSON.stringify(detail), result = projectWritingPreset(detail, source);
  expect(result.text.writing_goals).toBe('目标一\n目标二'); expect(result.omitted).toContain('parameter_hints');
  const pkg = personalBriefPackage(identity, result.text, result.source);
  expect(pkg.manifest.type).toBe('review'); expect(JSON.parse(pkg.manifest.provenance)).toMatchObject({ ...source, publisher_verified: false });
  expect(pkg.manifest.permissions).toEqual({ execute: false, network: false, manuscript_write: false, grant_capabilities: false, executable_plugins: 'DENY_ALL' });
  expect(pkg.content.sections).toHaveLength(4); expect(JSON.stringify(detail)).toBe(before);
});
it.each([{ validated: false }, { kind: 'workflow_templates' }, { sha256: 'b'.repeat(64) }, { plugin_id: 'other' }, { resource_id: 'other' }, { execution_supported: true }, { data: { ...data, writing_goals: 'wrong' } }, { data: { ...data, purpose: 'a'.repeat(8001) } }, { data: { ...data, schema_version: '2.0' } }, { data: { ...data, execution: 'supported' } }, { data: { ...data, parameter_hints: 'x'.repeat(128001) } }])('rejects unsupported/mismatched detail %j', patch => {
  expect(() => projectWritingPreset({ ...detail, ...patch }, source)).toThrow();
});
it('accepts self-written text with explicit identity and license only', () => {
  const text = { ...emptyBrief(), purpose: '自写' };
  expect(personalBriefPackage(identity, text).manifest.provenance).toBe('PERSONAL_SELF_WRITTEN_DECLARATION');
  expect(() => personalBriefPackage({ ...identity, license: '' }, text)).toThrow(/许可/);
  expect(() => personalBriefPackage({ ...identity, id: 'novel-craft-pack' }, text)).toThrow(/personal-/);
  expect(() => personalBriefPackage({ ...identity, version: 'v1' }, text)).toThrow(/版本/);
  expect(() => personalBriefPackage(identity, emptyBrief())).toThrow(/至少/);
  expect(() => personalBriefPackage(identity, { ...text, purpose: 'x'.repeat(8001) })).toThrow();
});
