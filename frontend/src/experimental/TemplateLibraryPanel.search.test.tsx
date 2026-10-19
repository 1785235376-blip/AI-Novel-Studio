// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { TemplateLibraryPanel } from './TemplateLibraryPanel';
import type { CatalogEntry, TemplateInstance, TemplatePackage } from './templateLibraryClient';

const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => experimentalClient('novel-search', { sessionToken: 'token-search', scope: { workspaceId: 'workspace', projectId: 'novel-search', storylineId: 'story', branchId: 'branch' } });
const remote = { remote_sync: 'DISABLED' };
const countLine = (matched: number) => screen.getByText(new RegExp('当前类型、收藏与搜索条件叠加后匹配 ' + matched + ' 个'));

function pkg(id: string, title: string, type: string, description: string, author: string): TemplatePackage {
  return { schema_version: 1, manifest: { id, version: '1.0.0', type, title, description, author, license: 'CC0-1.0', dependencies: [], provenance: 'ORIGINAL_SYNTHETIC_OFFLINE' }, content: { sections: [] } };
}
function entry(p: TemplatePackage, favorite = false): CatalogEntry {
  return { id: p.manifest.id, package: p, digest: 'a'.repeat(64), builtin: true, installed: false, version: 0, favorite, favorite_version: favorite ? 1 : 0, missing_dependencies: [] };
}
const outline = entry(pkg('alpha-outline', 'Alpha Outline', 'planning', 'Structured beats for chapters', 'Lin Wei'), true);
const dossier = entry(pkg('beta-dossier', 'Beta Dossier', 'character', 'Deep profiles', 'Ada Lovelace'));
const screenplay = entry(pkg('gamma-screenplay', '剧本模板', 'screenplay', '中文简介', '王小明'));
const agent = entry(pkg('delta-agent', 'Gamma Agent', 'agent', 'Tool declaration', 'Ada'));
const instance: TemplateInstance = { id: 'instance-one', version: 1, package_id: outline.id, package_version: '1.0.0', manifest: outline.package.manifest, content: { sections: [] }, edited: false, linked_target: null };

function transport(entries: CatalogEntry[], extended: CatalogEntry[] = [], copies: TemplateInstance[] = []) {
  return vi.fn(async (url: string) => {
    if (url.endsWith('/template-library')) return reply({ items: entries, types: [...new Set(entries.map(row => row.package.manifest.type))], extended_items: extended, extended_types: [...new Set(extended.map(row => row.package.manifest.type))], ...remote });
    if (url.endsWith('/instances')) return reply({ items: copies });
    throw new Error('Unhandled ' + url);
  });
}
function renderPanel(fetch: ReturnType<typeof transport>) {
  vi.stubGlobal('fetch', fetch);
  return render(<TemplateLibraryPanel client={client()} />);
}
const searchInput = () => screen.getByLabelText('搜索已加载模板') as HTMLInputElement;
const typeSelect = () => screen.getByLabelText('模板类型') as HTMLSelectElement;
const favoriteBox = () => screen.getByRole('checkbox', { name: '只看收藏' }) as HTMLInputElement;
async function ready(loaded = 4) { await screen.findByText(new RegExp('已加载 ' + loaded + ' 个模板')); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('matches loaded template title, description and author immediately and case-insensitively', async () => {
  renderPanel(transport([outline, dossier, screenplay], [agent])); await ready();
  fireEvent.change(searchInput(), { target: { value: 'OUTLINE' } });
  expect(screen.getByRole('option', { name: /Alpha Outline/ })).toBeTruthy();
  expect(screen.queryByRole('option', { name: /Beta Dossier/ })).toBeNull();
  countLine(1);
  fireEvent.change(searchInput(), { target: { value: 'deep PROfiles' } });
  expect(screen.getByRole('option', { name: /Beta Dossier/ })).toBeTruthy();
  expect(screen.queryByRole('option', { name: /Alpha Outline/ })).toBeNull();
  fireEvent.change(searchInput(), { target: { value: 'ada lovelace' } });
  expect(screen.getByRole('option', { name: /Beta Dossier/ })).toBeTruthy();
  countLine(1);
  fireEvent.change(searchInput(), { target: { value: '中文简介' } });
  expect(screen.getByRole('option', { name: /剧本模板/ })).toBeTruthy();
  countLine(1);
  fireEvent.change(searchInput(), { target: { value: 'AGENT' } });
  expect(screen.getByRole('option', { name: /Gamma Agent/ })).toBeTruthy();
  countLine(1);
});

it('trims surrounding whitespace and does not filter on whitespace-only input', async () => {
  renderPanel(transport([outline, dossier, screenplay], [agent])); await ready();
  fireEvent.change(searchInput(), { target: { value: '   ' } });
  countLine(4);
  expect(screen.queryByText('没有匹配的模板')).toBeNull();
  expect((screen.getByRole('button', { name: '清空搜索' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(searchInput(), { target: { value: '  beats  ' } });
  expect(screen.getByRole('option', { name: /Alpha Outline/ })).toBeTruthy();
  countLine(1);
});

it('treats missing optional manifest fields as non-matching instead of searchable null text', async () => {
  const partial: CatalogEntry = {
    ...entry(pkg('partial', 'Partial Title', 'planning', '', '')),
    package: { schema_version: 1, manifest: { id: 'partial', version: '1.0.0', type: 'planning', title: 'Partial Title', license: 'CC0-1.0', dependencies: [], provenance: 'ORIGINAL_SYNTHETIC_OFFLINE' } as unknown as TemplatePackage['manifest'], content: {} }
  };
  renderPanel(transport([partial]));
  await screen.findByText(/已加载 1 个模板/);
  fireEvent.change(searchInput(), { target: { value: 'undefined' } });
  countLine(0);
  expect(screen.getByText('没有匹配的模板')).toBeTruthy();
  fireEvent.change(searchInput(), { target: { value: 'null' } });
  countLine(0);
  fireEvent.change(searchInput(), { target: { value: 'partial' } });
  expect(screen.getByRole('option', { name: /Partial Title/ })).toBeTruthy();
  countLine(1);
});

it('intersects text search with the existing type filter', async () => {
  renderPanel(transport([outline, dossier, screenplay], [agent])); await ready();
  fireEvent.change(typeSelect(), { target: { value: 'planning' } });
  fireEvent.change(searchInput(), { target: { value: 'outline' } });
  countLine(1);
  expect(screen.getByRole('option', { name: /Alpha Outline/ })).toBeTruthy();
  fireEvent.change(searchInput(), { target: { value: 'dossier' } });
  countLine(0);
  expect(screen.getByText('没有匹配的模板')).toBeTruthy();
  fireEvent.change(searchInput(), { target: { value: '' } });
  countLine(1);
  expect(typeSelect().value).toBe('planning');
});

it('intersects text search with the existing favorite filter', async () => {
  renderPanel(transport([outline, dossier, screenplay], [agent])); await ready();
  fireEvent.click(favoriteBox());
  fireEvent.change(searchInput(), { target: { value: 'outline' } });
  countLine(1);
  expect(screen.getByRole('option', { name: /Alpha Outline/ })).toBeTruthy();
  fireEvent.change(searchInput(), { target: { value: 'dossier' } });
  countLine(0);
  expect(screen.getByText('没有匹配的模板')).toBeTruthy();
});

it('applies type, favorite and text filters together and counts the actual visible intersection', async () => {
  renderPanel(transport([outline, dossier, screenplay], [agent])); await ready();
  fireEvent.change(searchInput(), { target: { value: 'a' } });
  countLine(3);
  fireEvent.change(typeSelect(), { target: { value: 'planning' } });
  countLine(1);
  fireEvent.click(favoriteBox());
  countLine(1);
  expect(screen.getByRole('option', { name: /Alpha Outline/ })).toBeTruthy();
  fireEvent.change(searchInput(), { target: { value: 'beats' } });
  countLine(1);
  fireEvent.change(searchInput(), { target: { value: 'beta' } });
  countLine(0);
});

it('shows a distinct no-match prompt instead of a load failure or empty-library state', async () => {
  renderPanel(transport([outline, dossier], [], [instance])); await ready(2);
  fireEvent.change(searchInput(), { target: { value: 'zzzz' } });
  expect(screen.getByText('没有匹配的模板')).toBeTruthy();
  countLine(0);
  expect(screen.queryByText('暂无记录')).toBeNull();
  expect(screen.queryByText(/正在读取/)).toBeNull();
  expect(screen.queryByText(/读取或操作失败/)).toBeNull();
});

it('clears only the search term and restores the other active filters and results', async () => {
  renderPanel(transport([outline, dossier, screenplay], [agent])); await ready();
  fireEvent.change(typeSelect(), { target: { value: 'planning' } });
  fireEvent.click(favoriteBox());
  fireEvent.change(searchInput(), { target: { value: 'zzz' } });
  expect(screen.getByText('没有匹配的模板')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '清空搜索' }));
  expect(searchInput().value).toBe('');
  expect(typeSelect().value).toBe('planning');
  expect(favoriteBox().checked).toBe(true);
  countLine(1);
  expect(screen.getByRole('option', { name: /Alpha Outline/ })).toBeTruthy();
  expect(screen.queryByRole('option', { name: /Beta Dossier/ })).toBeNull();
});

it('never overwrites an unsaved project copy draft while searching or clearing', async () => {
  const fetch = transport([outline, dossier], [], [instance]);
  renderPanel(fetch); await ready(2);
  fireEvent.change(await screen.findByLabelText('选择项目模板副本'), { target: { value: instance.id } });
  const draft = await screen.findByLabelText('项目副本内容 JSON') as HTMLTextAreaElement;
  const custom = JSON.stringify({ sections: [{ key: 'goal', title: '目标', text: '未保存的手工修改' }] });
  fireEvent.change(draft, { target: { value: custom } });
  fireEvent.change(searchInput(), { target: { value: 'zzzz' } });
  expect(screen.getByText('没有匹配的模板')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '清空搜索' }));
  expect((screen.getByLabelText('项目副本内容 JSON') as HTMLTextAreaElement).value).toBe(custom);
  expect((screen.getByLabelText('选择项目模板副本') as HTMLSelectElement).value).toBe(instance.id);
  expect(fetch.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method && (init as RequestInit).method !== 'GET')).toBe(false);
});

it('performs local filtering without adding any network request', async () => {
  const fetch = transport([outline, dossier, screenplay], [agent]);
  renderPanel(fetch); await ready();
  const initialCalls = fetch.mock.calls.length;
  fireEvent.change(searchInput(), { target: { value: 'alpha' } });
  fireEvent.change(searchInput(), { target: { value: 'zzz' } });
  fireEvent.click(screen.getByRole('button', { name: '清空搜索' }));
  fireEvent.change(searchInput(), { target: { value: 'beats' } });
  fireEvent.click(screen.getByRole('button', { name: '清空搜索' }));
  expect(fetch.mock.calls.length).toBe(initialCalls);
  expect(fetch.mock.calls.every(([, init]) => !(init as RequestInit | undefined)?.method || (init as RequestInit).method === 'GET')).toBe(true);
});
