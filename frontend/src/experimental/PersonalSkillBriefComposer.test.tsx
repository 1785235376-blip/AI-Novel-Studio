// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../api';
import { PersonalSkillBriefComposer } from './PersonalSkillBriefComposer';
import { TemplateLibraryPanel } from './TemplateLibraryPanel';
import { experimentalClient } from './api';
const resource = { plugin_id: 'novel-craft-pack', resource_id: 'resources:scene.json', sha256: 'a'.repeat(64), kind: 'writing_presets', validated: true, execution_supported: false, name: 'Scene', data: { schema_version: '1.0', content_class: 'declarative_data', execution_supported: false, execution: 'not_supported', host_application: 'not_implemented', purpose: '预设用途', writing_goals: ['目标'], constraints: ['约束'], checklist: ['核对'], parameter_hints: {} } };
const catalog = { plugin_id: 'novel-craft-pack', items: [resource], total: 1, visible: true, validated: true, validation_status: 'VALIDATED', status: 'MANIFEST_ACTIVE', execution_supported: false, isolation: 'DENY_ALL' };
function mocks() { vi.spyOn(api, 'plugins').mockResolvedValue({ items: [{ id: 'novel-craft-pack', name: 'Novel', status: 'MANIFEST_ACTIVE' }, { id: 'disabled', status: 'DISABLED' }] }); vi.spyOn(api, 'pluginResources').mockResolvedValue(catalog); return vi.spyOn(api, 'pluginResource').mockResolvedValue(resource); }
function fill() { for (const [label, value] of [['个人简报标识', 'personal-test'], ['个人简报标题', '我的简报'], ['个人简报作者', '我'], ['个人简报许可声明', '自用'], ['简报用途', '自写用途']]) fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
async function select() { fireEvent.click(screen.getByText('读取可用预设包')); await screen.findByRole('option', { name: 'Novel' }); fireEvent.change(screen.getByLabelText('简报来源包'), { target: { value: 'novel-craft-pack' } }); fireEvent.click(screen.getByText('校验并列出写作预设')); await screen.findByRole('option', { name: 'Scene' }); fireEvent.change(screen.getByLabelText('简报来源预设'), { target: { value: resource.resource_id } }); }
const props = () => ({ busy: false, onPrepare: vi.fn(), onInvalidate: vi.fn(), onClose: vi.fn() });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('opens blank without reads, requires license and prepares JSON without install', () => {
  mocks(); const p = props(); render(<PersonalSkillBriefComposer {...p} />); expect(api.plugins).not.toHaveBeenCalled(); fill(); fireEvent.change(screen.getByLabelText('个人简报许可声明'), { target: { value: '' } }); fireEvent.click(screen.getByText('填入简报安装预览')); expect(p.onPrepare).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('个人简报许可声明'), { target: { value: '自用' } }); fireEvent.click(screen.getByText('填入简报安装预览')); expect(JSON.parse(p.onPrepare.mock.calls[0][0]).manifest).toMatchObject({ id: 'personal-test', license: '自用', type: 'review' });
});
it('adopts verified detail explicitly and preserves digest with omitted fields disclosed', async () => {
  const detail = mocks(), p = props(); render(<PersonalSkillBriefComposer {...p} />); fill(); await select(); expect(screen.queryByRole('option', { name: 'disabled' })).toBeNull(); expect(detail).not.toHaveBeenCalled(); fireEvent.click(screen.getByText('读取预设并替换四项内容'));
  await waitFor(() => expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe('预设用途')); expect(screen.getByText(/未采用字段/).textContent).toContain('parameter_hints'); fireEvent.click(screen.getByText('填入简报安装预览')); expect(JSON.parse(JSON.parse(p.onPrepare.mock.calls[0][0]).manifest.provenance)).toMatchObject({ pluginId: resource.plugin_id, resourceId: resource.resource_id, sha256: resource.sha256 });
});
it.each([{ validated: false, validation_status: 'DRIFT' }, { validated: false, validation_status: 'DUPLICATE' }, { validated: false, validation_status: 'REVIEW_REQUIRED' }, { validated: false, validation_status: 'PARTIAL' }, { status: 'DISABLED' }, { error_code: 'FAILURE' }, { total: 2, items: [resource, resource] }, { items: [null] }, { visible: 'yes' }, { invalid_resource_count: 1 }, { items: [{ ...resource, name: {} }] }])('blocks contradictory/malformed catalog %j', async patch => {
  mocks(); vi.mocked(api.pluginResources).mockResolvedValue({ ...catalog, ...patch } as typeof catalog); render(<PersonalSkillBriefComposer {...props()} />);
  fireEvent.click(screen.getByText('读取可用预设包')); await screen.findByRole('option', { name: 'Novel' }); fireEvent.change(screen.getByLabelText('简报来源包'), { target: { value: 'novel-craft-pack' } }); fireEvent.click(screen.getByText('校验并列出写作预设')); await screen.findByText(/来源读取失败/); expect(api.pluginResource).not.toHaveBeenCalled(); expect(screen.queryByRole('option', { name: 'Scene' })).toBeNull();
});
it('keeps text on changed SHA and late detail after hiding; blocks repeated reads', async () => {
  const detail = mocks().mockResolvedValue({ ...resource, sha256: 'b'.repeat(64) }), p = props(); const view = render(<PersonalSkillBriefComposer {...p} />); fill(); await select(); fireEvent.click(screen.getByText('读取预设并替换四项内容')); await screen.findByText(/来源读取失败/); expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe('自写用途');
  let resolve!: (value: typeof resource) => void; detail.mockReturnValue(new Promise(r => { resolve = r; })); const button = screen.getByText('读取预设并替换四项内容'); fireEvent.click(button); fireEvent.click(button); expect(detail).toHaveBeenCalledTimes(2); view.rerender(<PersonalSkillBriefComposer {...p} active={false} />); await act(async () => resolve(resource)); view.rerender(<PersonalSkillBriefComposer {...p} active />); expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe('自写用途');
});
function transport() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/template-library')) return new Response(JSON.stringify({ items: [], types: ['review'] }));
    if (url.endsWith('/instances')) return new Response(JSON.stringify({ items: [] }));
    if (url.endsWith('/preview')) return new Response(JSON.stringify({ package: JSON.parse(JSON.parse(init!.body as string).package), expected_version: 0, preview_digest: 'b'.repeat(64), diff: { lines: [], truncated: false }, missing_dependencies: [] }));
    return new Response(JSON.stringify({ detail: { code: 'VERSION_CONFLICT' } }), { status: 409 });
  });
}
const client = (name = 'one') => experimentalClient('novel-' + name, { sessionToken: 'token-' + name, scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'branch-' + name } });
it('preserves hidden draft, uses scoped versioned owner, invalidates edits and preserves conflicts', async () => {
  mocks(); const fetch = transport(); vi.stubGlobal('fetch', fetch); const view = render(<TemplateLibraryPanel client={client()} />); fireEvent.click(screen.getByText('编写个人写作简报')); fill(); fireEvent.click(screen.getByText('关闭简报编辑器')); fireEvent.click(screen.getByText('编写个人写作简报')); expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe('自写用途');
  fireEvent.click(screen.getByText('填入简报安装预览')); fireEvent.click(screen.getByText('预检并比较目录')); await screen.findByText('确认安装这个版本'); fireEvent.change(screen.getByLabelText('简报用途'), { target: { value: '新用途' } }); expect(screen.queryByText('确认安装这个版本')).toBeNull(); fireEvent.click(screen.getByText('填入简报安装预览')); fireEvent.click(screen.getByText('预检并比较目录')); await screen.findByText('确认安装这个版本'); const install = screen.getByText('确认安装这个版本'); fireEvent.click(install); fireEvent.click(install); await screen.findByText(/版本或来源已改变/);
  expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe('新用途'); const writes = fetch.mock.calls.filter(([url]) => url.endsWith('/install')); expect(writes).toHaveLength(1); expect(writes[0][1]?.headers).toMatchObject({ 'X-Session-Token': 'token-one', 'X-Branch-Id': 'branch-one' }); expect(JSON.parse(writes[0][1]!.body as string)).toMatchObject({ expected_version: 0, preview_digest: 'b'.repeat(64) }); view.rerender(<TemplateLibraryPanel client={client('two')} />); expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe('');
});
it('invalidates an intervening raw JSON preview when a deferred source read resolves', async () => {
  const detail = mocks(); let resolve!: (value: typeof resource) => void; detail.mockReturnValue(new Promise(r => { resolve = r; })); vi.stubGlobal('fetch', transport()); render(<TemplateLibraryPanel client={client()} />); fireEvent.click(screen.getByText('编写个人写作简报')); fill(); fireEvent.click(screen.getByText('填入简报安装预览')); await select(); fireEvent.click(screen.getByText('读取预设并替换四项内容')); fireEvent.click(screen.getByText('预检并比较目录')); await screen.findByText('确认安装这个版本'); await act(async () => resolve(resource)); expect(screen.queryByText('确认安装这个版本')).toBeNull();
});
it('saves a new personal brief, reloads it, then edits an independent copy through original owner endpoints', async () => {
  mocks(); let saved: any; let copy: any;
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    const reply = (value: unknown) => new Response(JSON.stringify(value));
    if (url.endsWith('/template-library')) return reply({ items: saved ? [saved] : [], types: ['review'] });
    if (url.endsWith('/preview')) return reply({ package: JSON.parse(body.package), expected_version: 0, preview_digest: 'b'.repeat(64), diff: { lines: [], truncated: false }, missing_dependencies: [] });
    if (url.endsWith('/install')) { const pkg = JSON.parse(body.package); saved = { id: pkg.manifest.id, package: pkg, digest: 'c'.repeat(64), builtin: false, installed: true, version: 1, favorite: false, favorite_version: 0, missing_dependencies: [] }; return reply(saved); }
    if (url.endsWith('/instances') && init?.method === 'POST') { copy = { id: 'copy-one', version: 1, package_id: saved.id, package_version: saved.package.manifest.version, manifest: saved.package.manifest, content: saved.package.content, edited: false, linked_target: null }; return reply(copy); }
    if (url.endsWith('/instances')) return reply({ items: copy ? [copy] : [] });
    if (url.endsWith('/instances/copy-one') && init?.method === 'PUT') { expect(body.expected_version).toBe(1); copy = { ...copy, version: 2, content: body.content, edited: true }; return reply(copy); }
    throw new Error('Unexpected owner call ' + url);
  }); vi.stubGlobal('fetch', fetch); render(<TemplateLibraryPanel client={client()} />); fireEvent.click(screen.getByText('编写个人写作简报')); fill(); fireEvent.click(screen.getByText('填入简报安装预览')); fireEvent.click(screen.getByText('预检并比较目录')); await screen.findByText('确认安装这个版本'); fireEvent.click(screen.getByText('确认安装这个版本')); await screen.findByRole('option', { name: '我的简报 · 1.0.0' });
  fireEvent.change(screen.getByLabelText('选择本地模板'), { target: { value: 'personal-test' } }); const create = screen.getByText('复制为本项目版本'); fireEvent.click(create); fireEvent.click(create); await screen.findByLabelText('项目副本内容 JSON'); const content = { sections: [{ key: 'purpose', title: '用途', text: '独立修改' }] }; fireEvent.change(screen.getByLabelText('项目副本内容 JSON'), { target: { value: JSON.stringify(content) } }); fireEvent.click(screen.getByText('保存副本编辑')); await screen.findByText(/项目副本已保存/);
  expect(copy.content).toEqual(content); expect(saved.package.content.sections[0].text).toBe('自写用途'); expect(fetch.mock.calls.filter(([url, init]) => url.endsWith('/instances') && init?.method === 'POST')).toHaveLength(1); expect(fetch.mock.calls.every(([url]) => url.includes('/novels/novel-one/experimental/template-library'))).toBe(true); expect(api.plugins).not.toHaveBeenCalled();
});
