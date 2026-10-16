// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { TemplateLibraryPanel } from './TemplateLibraryPanel';
import type { TemplateInstance } from './templateLibraryClient';
const content = { sections: [{ key: 'purpose', title: '用途', text: '原始简报' }, { key: 'goal', title: '目标', text: '保持目标' }] };
const manifest = { id: 'personal-brief', title: '个人简报', version: '1.0.0', type: 'review', description: '', author: '作者甲', license: '个人声明', dependencies: [], provenance: 'PERSONAL_TEXT_PROJECTION:sha256' };
const initial: TemplateInstance = { id: 'copy-one', version: 1, package_id: manifest.id, package_version: '1.0.0', manifest, content, edited: false, linked_target: null };
const client = () => experimentalClient('novel-one', { sessionToken: 'token-one', scope: { workspaceId: 'workspace-one', projectId: 'novel-one', storylineId: 'story-one', branchId: 'branch-one' } });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
function transport(reject = false) {
  let row = initial;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/template-library')) return reply({ items: [{ id: manifest.id, package: { schema_version: 1, manifest, content }, digest: 'a'.repeat(64), builtin: false, installed: true, version: 1, favorite: false, favorite_version: 0, missing_dependencies: [] }], types: ['review'] });
    if (url.endsWith('/instances')) return reply({ items: [row] });
    if (url.endsWith('/history')) return reply({ items: [{ version: 1, package_version: '1.0.0', content }] });
    if (url.endsWith('/copy-one') && init?.method === 'PUT') {
      if (reject) return reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409);
      const body = JSON.parse(init.body as string); expect(body.expected_version).toBe(row.version);
      row = { ...row, version: row.version + 1, content: body.content, edited: true }; return reply(row);
    }
    throw Error('Unexpected request: ' + url);
  });
}
async function selectCopy() {
  await waitFor(() => expect((screen.getByLabelText('选择项目模板副本') as HTMLSelectElement).options).toHaveLength(2));
  fireEvent.change(screen.getByLabelText('选择项目模板副本'), { target: { value: initial.id } });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('saves structured edits through original CAS owner and reopens content and provenance', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); const c = client(); let view = render(<TemplateLibraryPanel client={c} />); await selectCopy();
  fireEvent.change(screen.getByLabelText('副本简报：用途'), { target: { value: '改后的中文简报' } });
  expect(JSON.parse((screen.getByLabelText('项目副本内容 JSON') as HTMLTextAreaElement).value).sections[0].text).toBe('改后的中文简报');
  fireEvent.click(screen.getByRole('button', { name: '保存副本编辑' })); await screen.findByText(/内容 v2/);
  const writes = fetch.mock.calls.filter(([, init]) => init?.method === 'PUT'); expect(writes).toHaveLength(1);
  expect(writes[0][1]?.headers).toMatchObject({ 'X-Session-Token': 'token-one', 'X-Branch-Id': 'branch-one' });
  expect(JSON.parse(writes[0][1]!.body as string)).toEqual({ expected_version: 1, content: { sections: [{ ...content.sections[0], text: '改后的中文简报' }, content.sections[1]] } });
  view.unmount(); view = render(<TemplateLibraryPanel client={c} />); await selectCopy();
  expect((screen.getByLabelText('副本简报：用途') as HTMLTextAreaElement).value).toBe('改后的中文简报');
  expect(screen.getByText(/作者甲.*个人声明.*PERSONAL_TEXT_PROJECTION:sha256/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '查看副本历史' })); await screen.findByLabelText('要恢复的副本历史版本');
  fireEvent.change(screen.getByLabelText('要恢复的副本历史版本'), { target: { value: '1' } });
  expect(screen.getByText(/历史 v1 → 已保存 v2/)).toBeTruthy();
  expect(screen.getByText('历史版本中的片段')).toBeTruthy(); expect(screen.getByText('已保存版本中的片段')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('副本简报：用途'), { target: { value: '未保存修改' } });
  expect((screen.getByRole('button', { name: '恢复为新的副本版本' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('选择项目模板副本') as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('选择本地模板'), { target: { value: manifest.id } });
  expect((screen.getByRole('button', { name: '复制为本项目版本' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃未保存的副本编辑' }));
  expect((screen.getByLabelText('选择项目模板副本') as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText('副本简报：用途') as HTMLTextAreaElement).value).toBe('改后的中文简报');
  expect(fetch.mock.calls.some(([url]) => /execute|generate|install|revert/.test(url))).toBe(false);
});
it('retains draft on conflict and resets with a new client', async () => {
  vi.stubGlobal('fetch', transport(true)); const view = render(<TemplateLibraryPanel client={client()} />); await selectCopy();
  fireEvent.change(screen.getByLabelText('副本简报：用途'), { target: { value: '冲突草稿' } });
  fireEvent.click(screen.getByRole('button', { name: '保存副本编辑' })); await screen.findByText(/版本或来源已改变/);
  expect((screen.getByLabelText('副本简报：用途') as HTMLTextAreaElement).value).toBe('冲突草稿');
  view.rerender(<TemplateLibraryPanel client={client()} />); await selectCopy();
  expect((screen.getByLabelText('副本简报：用途') as HTMLTextAreaElement).value).toBe('原始简报');
});
it('preserves invalid JSON and hides structured controls', async () => {
  vi.stubGlobal('fetch', transport()); render(<TemplateLibraryPanel client={client()} />); await selectCopy();
  fireEvent.change(screen.getByLabelText('项目副本内容 JSON'), { target: { value: '{' } });
  expect(screen.queryByLabelText('副本简报：用途')).toBeNull();
  expect((screen.getByLabelText('项目副本内容 JSON') as HTMLTextAreaElement).value).toBe('{');
});
