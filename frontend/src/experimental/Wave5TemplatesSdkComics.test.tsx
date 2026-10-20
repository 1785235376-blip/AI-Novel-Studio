// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { TemplateLibraryPanel } from './TemplateLibraryPanel';
import { DeclarativeAgentsPanel } from './DeclarativeAgentsPanel';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import type { AuthoredWorkflow } from './declarativeAgentsClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (nid = 'wave5') => experimentalClient(nid, { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: nid, storylineId: 's', branchId: 'b' } });
const workflow: AuthoredWorkflow = { agent: { title: 'Original approved-definition seam', purpose: '', role_prompt: '', input_schema: { fields: [{ name: 'source_text', type: 'string', required: true, max_length: 8000 }] }, output_schema: { fields: [{ name: 'draft', type: 'string', required: true, max_length: 8000 }] }, allowed_tools: ['draft_prepare'], model_route: null, review_required: true, max_steps: 8, timeout_seconds: 30, max_output_bytes: 64000, max_cost_microusd: 0 }, nodes: [{ id: 'prepare', type: 'draft_prepare', name: 'Prepare' }, { id: 'review', type: 'manual_approval', name: 'Review' }, { id: 'artifact', type: 'review_artifact', name: 'Artifact' }], edges: [{ source: 'prepare', target: 'review' }, { source: 'review', target: 'artifact' }] };
const entry = (type: string) => ({ id: `synthetic-${type}`, package: { schema_version: 1, manifest: { id: `synthetic-${type}`, version: '1.0.0', title: `Synthetic ${type}`, type, description: 'Offline example', author: 'Synthetic', license: 'CC0-1.0', dependencies: type === 'agent' ? ['declarative_agents_v2'] : [], provenance: 'ORIGINAL_SYNTHETIC_OFFLINE', compatibility: { protocol: 'LOCAL_BOUNDED_JSON_V1', schema_versions: [1], import_mode: 'READ_ONLY_DECLARATION' }, permissions: { execute: false, network: false, manuscript_write: false, grant_capabilities: false, executable_plugins: 'DENY_ALL' } }, content: type === 'agent' ? workflow : { sections: [{ key: 'premise', title: 'Premise', text: 'Synthetic bounded brief.' }] } }, digest: 'a'.repeat(64), builtin: true, installed: false, version: 0, favorite: false, favorite_version: 0, missing_dependencies: [] });
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:wave5'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('combines legacy and extended catalogs, filters exact types and copies Agent to original definition without execution', async () => {
  const navigate = vi.fn(); const agent = entry('agent');
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/template-library')) return reply({ items: [entry('character')], types: ['character'], extended_items: ['novel', 'genre', 'world', 'agent', 'story_structure'].map(entry), extended_types: ['novel', 'genre', 'world', 'agent', 'story_structure'] });
    if (url.endsWith('/instances') && init.method === 'POST') return reply({ id: 'copy', version: 1, package_id: agent.id, package_version: '1.0.0', manifest: agent.package.manifest, content: agent.package.content, edited: false, linked_target: { id: 'original-definition', version: 1, feature: 'declarative_agents_v2' } }, 201);
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch); render(<StrictMode><TemplateLibraryPanel client={client()} onNavigate={navigate} /></StrictMode>);
  await screen.findByRole('option', { name: 'Synthetic agent · 1.0.0' });
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('模板类型'), { target: { value: 'agent' } });
  expect(screen.queryByRole('option', { name: 'Synthetic novel · 1.0.0' })).toBeNull();
  fireEvent.change(screen.getByLabelText('选择本地模板'), { target: { value: agent.id } });
  expect(screen.getByText(/只读声明导入/).textContent).toContain('权限授予：无');
  fireEvent.click(screen.getByRole('button', { name: '复制为本项目版本' }));
  fireEvent.click(await screen.findByRole('button', { name: '打开已创建记录的功能' }));
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'original-definition', feature: 'declarative_agents_v2' });
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(1);
  expect(JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'POST')![1].body))).toMatchObject({ package_id: agent.id, package_digest: agent.digest });
});

it('Agent runtime and capability requirements persist alongside finite input/output schemas, never granting a runtime', async () => {
  const contract = { model_capability: 'NONE', capability_requirements: ['LOCAL_RULES'], runtime_requirement: 'TRUSTED_IN_PROCESS_LOCAL', input_schema: workflow.agent.input_schema, output_schema: workflow.agent.output_schema, review_required: true, executable_plugins: 'DENY_ALL', permission_grants: [], real_model_verification: 'NOT_RUN' };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply({ tools: ['draft_prepare'], node_types: ['draft_prepare', 'manual_approval', 'review_artifact'], model_routes: [], default_definition: workflow, chapters: [], sdk_contract: contract });
    if (url.endsWith('/definitions') && init.method === 'POST') return reply({ id: 'definition', version: 1, definition: JSON.parse(String(init.body)).definition, definition_digest: 'a'.repeat(64) }, 201);
    if (url.endsWith('/preflight')) return reply({ valid: true, execution_available: true, topological_order: ['prepare', 'review', 'artifact'], blockers: [], adapter_contract: contract });
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch); render(<DeclarativeAgentsPanel client={client()} />);
  fireEvent.change(await screen.findByLabelText('Adapter 运行时要求'), { target: { value: 'TRUSTED_IN_PROCESS_LOCAL' } });
  fireEvent.click(screen.getByLabelText('LOCAL_RULES'));
  fireEvent.click(screen.getByRole('button', { name: '保存 Agent 定义' }));
  await screen.findByText(/已保存定义 definition · v1/);
  const data = JSON.parse(String(fetch.mock.calls.find(([url, init]) => url.endsWith('/definitions') && init.method === 'POST')![1].body));
  expect(data.definition.agent).toMatchObject({ capability_requirements: ['LOCAL_RULES'], runtime_requirement: 'TRUSTED_IN_PROCESS_LOCAL', review_required: true, input_schema: workflow.agent.input_schema, output_schema: workflow.agent.output_schema });
  fireEvent.click(screen.getByRole('button', { name: '验证 Workflow 图与权限' }));
  await screen.findByText('Adapter 能力、运行时与 Schema 合约');
  expect(fetch.mock.calls.some(([url]) => /execute|dispatch|register/.test(url))).toBe(false);
});

it('Comic briefs and appearance refs use approved versioned original assets and removing a character removes its reference', async () => {
  const source = { id: 'screenplay', title: 'Comic source', edit_version: 4, shots: [{ id: 'shot', number: 1, scene_id: 'scene' }] };
  const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
  let saved: unknown;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply({ screenplays: [source], characters: [{ id: 'alice', name: 'Alice' }], assets: [{ id: 'reference', filename: 'Approved appearance.png', version: 7, approved: true }, { id: 'pending', filename: 'Pending.png', version: 1, approved: false }], presets: { PAGE: preset, WEBTOON: { ...preset, height: 2400 } }, renderer: { available: true }, font: { available: true } });
    if (init.method === 'POST') { saved = JSON.parse(String(init.body)); return reply({ id: 'layout', version: 1, status: 'DRAFT', stale: false, document: saved, history_versions: [] }, 201); }
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch); const view = render(<ComicLayoutsPanel client={client()} />);
  await screen.findByRole('option', { name: /Comic source/ });
  fireEvent.change(screen.getByLabelText('漫画来源剧本'), { target: { value: source.id } });
  fireEvent.change(screen.getByLabelText('格框 1 图片简报'), { target: { value: 'Alice studies the map.' } });
  const characters = screen.getByLabelText('格框 1 关联人物') as HTMLSelectElement;
  characters.options[0].selected = true; fireEvent.change(characters);
  const appearances = screen.getByLabelText('格框 1 Alice 外观参考') as HTMLSelectElement;
  expect(Array.from(appearances.options, o => o.value)).toEqual(['', 'reference']);
  fireEvent.change(appearances, { target: { value: 'reference' } });
  fireEvent.change(screen.getByLabelText('格框 1 Alice 外观说明'), { target: { value: 'Keep the blue coat.' } });
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(saved).toBeDefined());
  expect(saved).toMatchObject({ screenplay_id: 'screenplay', expected_screenplay_version: 4, panels: [{ shot_id: 'shot', image_brief: 'Alice studies the map.', appearance_references: [{ character_id: 'alice', asset_id: 'reference', expected_asset_version: 7, note: 'Keep the blue coat.' }] }] });
  await screen.findByText(/布局已保存为待审草稿/);
  characters.options[0].selected = false; fireEvent.change(characters);
  expect(screen.queryByLabelText('格框 1 Alice 外观参考')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect((screen.getByLabelText('格框 1 Alice 外观参考') as HTMLSelectElement).value).toBe('reference');
  expect(fetch.mock.calls.some(([url]) => /generate|execute|dispatch/.test(url))).toBe(false);
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {}))); view.rerender(<ComicLayoutsPanel client={client('other')} />);
  expect(screen.queryByDisplayValue('Alice studies the map.')).toBeNull();
});

it('an explicitly stale backend record hides an already opened private comic brief after refresh', async () => {
  const source = { id: 'screenplay', title: 'Comic source', edit_version: 4, shots: [{ id: 'shot', number: 1, scene_id: 'scene' }] };
  const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
  const document = { title: 'Existing comic', screenplay_id: source.id, expected_screenplay_version: 4, preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', ...preset, panels: [{ id: 'panel', shot_id: 'shot', order: 1, x: 24, y: 24, width: 752, height: 1000, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', bubbles: [], image_brief: 'Private stored brief', appearance_references: [] }] };
  let stale = false;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? { screenplays: [source], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } } : { items: [stale ? { id: 'layout', version: 1, status: 'DRAFT', stale: true } : { id: 'layout', version: 1, status: 'DRAFT', stale: false, document, history_versions: [] }] })));
  render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开布局 Existing comic' }));
  expect((screen.getByLabelText('格框 1 图片简报') as HTMLTextAreaElement).value).toBe('Private stored brief');
  stale = true; fireEvent.click(screen.getByRole('button', { name: '刷新漫画来源与记录' }));
  await screen.findByText('来源、授权或图片已变化，旧布局内容和导出已隐藏。');
  expect(screen.queryByLabelText('格框 1 图片简报')).toBeNull();
  expect(screen.queryByDisplayValue('Private stored brief')).toBeNull();
});
