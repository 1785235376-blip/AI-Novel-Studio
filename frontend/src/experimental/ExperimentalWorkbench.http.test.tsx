// @vitest-environment jsdom
// Optional real-HTTP integration. This is React/jsdom, never browser evidence.
// Start an isolated File backend with explicit Experimental flags, then set
// R3_HTTP_BASE=http://127.0.0.1:8019 and run this file with Vitest.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
const base = process.env.R3_HTTP_BASE;
const transport = globalThis.fetch;
const flags = { experimental: true, default_enabled: false as const, features: Object.fromEntries(['advanced_planning_v2', 'semantic_import_v2', 'world_character_engines_v2', 'unified_review_inbox', 'agent_team_recipes', 'media_adapter_registry', 'cover_storyboard_generation', 'visual_embeddings', 'audiobook_v2'].map(key => [`experimental.${key}`, true])) };
async function api(path: string, data?: unknown, method = 'POST') { const response = await transport(base + '/api' + path, { method: data === undefined ? 'GET' : method, headers: { 'Content-Type': 'application/json' }, ...(data === undefined ? {} : { body: JSON.stringify(data) }) }); const value = await response.json(); expect(response.ok, JSON.stringify(value)).toBe(true); return value; }
function fill(name: string, value: string) { fireEvent.change(screen.getByLabelText(name, { exact: true }), { target: { value } }); }
async function click(name: string) { await waitFor(() => expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(screen.getByRole('button', { name })); }
async function settled() { await waitFor(() => expect(screen.queryByRole('alert')).toBeNull()); }
let novel: any, chapter: any;
describe.skipIf(!base)('Experimental React with real HTTP File backend (not a browser)', () => {
  beforeEach(async () => {
    // Node's transport cannot consume jsdom AbortSignal; cancellation is covered by unit/browser tests.
    vi.stubGlobal('fetch', (url: string | URL | Request, options?: RequestInit) => transport(typeof url === 'string' && url.startsWith('/') ? base + url : url, { ...options, signal: undefined }));
    novel = await api('/novels', { title: `R3 HTTP fixture ${Date.now()}` });
    chapter = await api(`/novels/${novel.id}/chapters`, { title: 'Synthetic', content: 'Alice said hello in Harbor. One day the secret would return.' });
    chapter = await api(`/chapters/${chapter.id}`);
    render(<ExperimentalWorkbench novelId={novel.id} chapter={chapter} context={{ sessionToken: '' }} flags={flags} />);
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  it('creates a hierarchy, saves and compares real Mock proposals without manuscript changes', async () => {
    fill('规划名称', 'HTTP planning'); await click('创建项目规划'); await screen.findByRole('button', { name: 'PROJECT · HTTP planning' });
    await click('添加 VOLUME 子节点'); await screen.findByRole('heading', { name: '编辑 VOLUME' }); await click('添加 CHAPTER 子节点'); await screen.findByRole('heading', { name: '编辑 CHAPTER' }); await click('添加 SCENE 子节点'); await screen.findByRole('heading', { name: '编辑 SCENE' });
    fill('目标', 'Synthetic goal'); await click('保存节点'); await screen.findByText('节点已保存');
    fill('规划模板', 'multiple-endings'); await click('生成 Mock 双方案'); const first = await screen.findByRole('article', { name: '方案 Mock option 1' }); const second = await screen.findByRole('article', { name: '方案 Mock option 2' });
    fireEvent.click(within(first).getByRole('checkbox')); fireEvent.click(within(second).getByRole('checkbox')); await click('比较已选方案'); await screen.findByRole('region', { name: '规划方案比较' });
    await waitFor(() => expect((within(first).getByRole('button', { name: '批准规划' }) as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(within(first).getByRole('button', { name: '批准规划' })); await waitFor(() => expect(first.textContent).toContain('APPROVED'));
    // Approval advances the same node. Retain edits and explicitly rebase before saving again.
    fill('目标', 'Retained post-approval draft');
    await screen.findByRole('region', { name: '规划节点版本恢复' });
    await click('刷新实验记录');
    expect((screen.getByLabelText('目标', { exact: true }) as HTMLTextAreaElement).value).toBe('Retained post-approval draft');
    await click('保留草稿并更新保存基线'); await screen.findByText('草稿已保留并更新保存基线，尚未提交'); await click('保存节点');
    await screen.findByText('节点已保存');
    const graphs = await api(`/novels/${novel.id}/experimental/planning/graphs`);
    const stored = await api(`/novels/${novel.id}/experimental/planning/graphs/${graphs.items[0].id}`);
    expect(stored.nodes.find((row: any) => row.level === 'SCENE').fields.goal).toBe('Retained post-approval draft');
    expect((await api(`/chapters/${chapter.id}`)).content).toBe(chapter.content); await settled();
  });
  it('runs actual chunk extraction and verified review/commit', async () => {
    await click('长篇导入'); await click('创建分块导入'); await screen.findByText(/QUEUED · v1/); await click('暂停导入'); await waitFor(() => expect(screen.getByRole('region', { name: '导入任务状态' }).textContent).toContain('PAUSED')); await click('恢复导入'); await screen.findByRole('button', { name: '处理下一分块' }); await click('处理下一分块');
    await waitFor(() => expect(screen.getByRole('region', { name: '导入任务状态' }).textContent).toContain('NEEDS_REVIEW')); const candidates = await screen.findAllByRole('article');
    for (const row of candidates) fireEvent.click(within(row).getByRole('checkbox'));
    await click('批量批准已选候选'); await screen.findByText('所选候选均已通过来源校验与审核'); fireEvent.click(screen.getByRole('checkbox', { name: /我已核对/ })); await click('提交已批准导入');
    await waitFor(() => expect(screen.getByRole('region', { name: '导入任务状态' }).textContent).toContain('COMMITTED')); await settled();
  });
  it('reviews a world record through the actual unified domain dispatcher', async () => {
    await click('世界与人物'); fill('世界记录标题', 'HTTP historical event'); await click('创建世界候选'); await screen.findByRole('article', { name: '世界记录 HTTP historical event' });
    await click('统一审核'); const row = await screen.findByRole('article', { name: '审核项 world HTTP historical event' }); fireEvent.click(within(row).getByRole('button', { name: '批准此审核项' })); await waitFor(() => expect(row.textContent).toContain('APPROVED'));
    const canon = await api(`/novels/${novel.id}/experimental/world/canon`); expect(canon.items).toHaveLength(1);
    await click('世界与人物'); await click('检查世界连续性');
    expect((await screen.findByRole('region', { name: '世界连续性结果' })).textContent).toContain('DETERMINISTIC_RULES'); await settled();
  });
  it('executes the actual team recipe and leaves a reviewed artifact', async () => {
    await click('创作团队'); fill('团队任务指令', 'Synthetic outline'); await click('创建团队任务'); const row = await screen.findByRole('article', { name: '团队任务 outline_chapter_editor' }); fireEvent.click(within(row).getByRole('button', { name: '执行本地 Recipe' })); await screen.findByRole('button', { name: '人工批准团队产物' }); await click('人工批准团队产物'); await waitFor(() => expect(row.textContent).toContain('SUCCEEDED')); await settled();
  });
  it('creates and approves a real mock-media payload and exposes NOT_CONFIGURED embeddings', async () => {
    // URL lifetime stub only: HTTP response and image bytes are real; jsdom has no decoder.
    vi.stubGlobal('URL', class extends URL { static createObjectURL() { return 'blob:synthetic-ui'; } static revokeObjectURL() {} });
    await click('封面与分镜'); fill('封面标题', 'Synthetic cover'); await click('保存封面 Brief'); await screen.findByText('封面 Brief 已保存'); await click('创建 Mock 图像任务'); await screen.findByRole('button', { name: '执行 Mock 图像任务' }); await click('执行 Mock 图像任务'); const row = await screen.findByRole('article', { name: '媒体候选 1' }); fireEvent.click(within(row).getByRole('button', { name: '批准媒体为资产' })); await waitFor(() => expect(row.textContent).toContain('APPROVED'));
    expect((await api(`/novels/${novel.id}/assets`)).length).toBe(1); await click('视觉 Embedding'); await screen.findByText('NOT_CONFIGURED'); await settled();
  });
  it('prepares profiles, narration, reviewed timeline and honest duration data', async () => {
    await click('有声书 V2'); fill('声音 Profile 名称', 'Synthetic narrator'); fill('声音 Provider ID', 'fixture'); fill('声音 Model ID', 'fixture'); fill('Voice ID', 'fixture'); fill('声音许可说明', 'Synthetic only'); await click('保存声音 Profile'); await screen.findByText('声音 Profile 已保存；音质尚未验证'); await click('保存人物声音映射'); await screen.findByText('人物声音映射已保存'); await click('创建对白序列计划'); await screen.findByRole('region', { name: '有声计划详情' });
    await click('查看时长清单'); await screen.findByText('实测时长清单'); await click('批准有声计划'); await waitFor(() => expect(screen.getByRole('region', { name: '有声计划详情' }).textContent).toContain('APPROVED')); expect((await api(`/novels/${novel.id}/experimental/audiobook/plans`)).items[0].duration_ms).toBeNull(); await settled();
  });
});
