// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, type Chapter } from './api';
import { drafts, conflicts, conflictResolutionDrafts } from './drafts';
import { useStudio } from './store';
import { generationRecovery } from './generationRecovery';
vi.mock('./Editor', () => ({ ChapterEditor: ({ content, onChange }: any) => <textarea aria-label="Test chapter editor" value={content} onChange={event => onChange(event.target.value, doc(event.target.value))} /> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, sidebar, onModuleChange, onGlobalSearch }: any) => <><button onClick={() => onModuleChange('IMAGE')}>Switch image</button><button onClick={onGlobalSearch}>Global search</button>{sidebar}{main}</> }));
vi.mock('./ui/ModuleWorkspaceRoutes', () => ({ ModuleWorkspaceRoutes: () => <p>Destination image module</p> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: () => null }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', () => ({ FeatureLauncher: ({ onSelect }: any) => <><button onClick={() => onSelect('experimental')}>Open style tools</button><button onClick={() => onSelect('overview')}>Open overview</button></> }));
vi.mock('./experimental/DeferredExperimentalWorkbench', async () => {
 const { ExperimentalWorkbench } = await import('./experimental/ExperimentalWorkbench');
 return { DeferredExperimentalWorkbench: (props: any) => <><button onClick={() => props.onNavigate({ kind: 'generation', id: 'author-two', chapter_id: 'recovery:2', version: 10 })}>Open guarded job</button><ExperimentalWorkbench {...props} requestedTab={props.requestedTab || 'style_dna_v2'} /></> };
});
function doc(text: string) { return { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] }; }
function chapter(content = 'SAVED', version = 3, id = 'recovery:1'): Chapter {
  return { id, novel_id: 'recovery', number: 1, title: 'Synthetic chapter', content, document: doc(content), version, word_count: content.length, status: 'DRAFT' };
}
function taskState(id: string, status = 'COMPLETED', output = 'READY FIRST', baseVersion = 3) { return { id, novel_id: 'recovery', chapter_id: 'recovery:1', status, output, base_chapter_version: baseVersion }; }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const clients: QueryClient[] = [];
let navigationController: AbortController | undefined;
function setup(enabled = true, strict = false, creative = false) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], [{ id: 'recovery', title: 'Synthetic' }]);
  query.setQueryData(['chapter', 'file', 'recovery:1'], chapter());
  query.setQueryData(['chapter', 'file', 'recovery:2'], chapter('SECOND', 10, 'recovery:2'));
  query.setQueryData(['chapters', 'file', 'recovery'], [chapter(), chapter('SECOND', 10, 'recovery:2')]);
  query.setQueryData(['archived-chapters', 'file', 'recovery'], []);
  query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'recovery'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'recovery'], { current_words: 0, target_words: 10, current_chapters: 2, target_chapters: 3, words_progress: 0 });
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.narrative_production_v2': creative, 'experimental.writing_recovery_v2': false, 'experimental.style_dna_v2': true, 'experimental.workspace_tools_v2': enabled } });
  const app = <QueryClientProvider client={query}><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{app}</StrictMode> : app);
  return { query, view };
}
const editor = () => screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement;
function edit(text: string) { fireEvent.change(editor(), { target: { value: text } }); }
beforeEach(() => {
  navigationController = undefined;
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: 'recovery', chapterId: 'recovery:1', textModel: null });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'PUT' || init?.method === 'POST') return saveResponse(url, init);
    return new Response(JSON.stringify(url.endsWith('/creative/capabilities') ? { enabled: true, can_mutate: true, modes: ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD', 'PRODUCTION'] } : url.endsWith('/style-analysis/catalog') ? styleCatalog : url.includes('/workspace/resume') ? { item: null } : { items: [] }), { status: 200 });
  }));
  vi.spyOn(api, 'generate').mockRejectedValue(new Error('must not create a generation'));
  vi.spyOn(api, 'accept').mockRejectedValue(new Error('must not accept'));
  vi.spyOn(api, 'novels').mockResolvedValue([{ id: 'recovery', title: 'Synthetic' }] as any);
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'chapters').mockResolvedValue([chapter()]);
  vi.spyOn(api, 'job').mockImplementation(async id => {
    const saved = generationRecovery.load('file', 'recovery:1');
    const variant = saved?.variants?.find(item => item.id === id);
    return taskState(id, variant ? (variant.status === 'ready' ? 'COMPLETED' : variant.status === 'failed' ? 'FAILED' : 'GENERATING') : saved?.job?.status ?? 'COMPLETED',
      variant?.output ?? saved?.job?.output ?? 'READY FIRST', variant?.baseChapterVersion ?? saved?.baseChapterVersion ?? 3);
  });
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals();
  ['recovery:1', 'recovery:2'].forEach(id => { drafts.remove(id); conflicts.remove(id); conflicts.clearHistory(id); conflictResolutionDrafts.remove(id); });
  localStorage.clear(); sessionStorage.clear();
});
const profile = { id: 'style', title: 'Original', instructions: 'Human rules', rules: [], chapter_ids: [], character_ids: [], version: 1, status: 'DRAFT', style_dna: { schema_version: 1, global_rules: { color: 'Amber' }, overrides: [] } };
const styleCatalog = { styles: [profile], chapters: [], characters: [], operations: ['continue'] };
let saveResponse: (url: string, init?: RequestInit) => Promise<Response>;
beforeEach(() => { saveResponse = async () => new Response(JSON.stringify({ ...profile, version: 2 }), { status: 200 }); });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
async function openStyle(strict = false) {
  const result = setup(true, strict); click('Open style tools');
  await screen.findByRole('option', { name: /Original/ });
  fireEvent.change(screen.getByLabelText('Style DNA 档案'), { target: { value: 'style' } });
  fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'PRIVATE_DRAFT' } });
  return result;
}
it.each(['Switch image', 'Open overview', 'Global search', '切换本机作品'])('protects original App %s before any transition', async name => {
  await openStyle(); click(name); expect(screen.getByRole('region', { name: 'Style DNA 未保存修改' })).toBeTruthy();
  expect(useStudio.getState().novelId).toBe('recovery'); expect(screen.getByDisplayValue('PRIVATE_DRAFT')).toBeTruthy();
  click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('PRIVATE_DRAFT')).toBeTruthy();
  click(name); click('放弃 Style DNA 修改并离开');
  await waitFor(() => expect(screen.queryByDisplayValue('PRIVATE_DRAFT')).toBeNull());
});
it('saves through original STYLE endpoint before leaving and keeps manuscript unchanged', async () => {
  await openStyle(true); click('Open overview'); click('保存 Style DNA 后离开');
  await waitFor(() => expect(screen.queryByDisplayValue('PRIVATE_DRAFT')).toBeNull());
  const writes = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'PUT');
  expect(writes).toHaveLength(1); expect(JSON.parse(String(writes[0][1]?.body))).toMatchObject({ expected_version: 1, style_dna: { global_rules: { color: 'PRIVATE_DRAFT' } } });
  expect(editor().value).toBe('SAVED');
});
it('late save after cancel never leaves the original editor', async () => {
  const pending = deferred<Response>(); saveResponse = () => pending.promise;
  await openStyle(); click('Open overview'); click('保存 Style DNA 后离开'); click('继续编辑 Style DNA');
  await act(async () => pending.resolve(new Response(JSON.stringify({ ...profile, version: 2 }), { status: 200 })));
  expect(screen.getByLabelText('Style DNA 档案')).toBeTruthy();
});
it('failure retains the private draft; permission revocation quarantines it and cancels intent', async () => {
  saveResponse = async () => new Response(JSON.stringify({ code: 'VERSION_CONFLICT' }), { status: 409 });
  const { query } = await openStyle(); click('Open overview'); click('保存 Style DNA 后离开');
  await screen.findByText(/Style DNA 尚未确认保存/); expect(screen.getByDisplayValue('PRIVATE_DRAFT')).toBeTruthy();
  act(() => query.setQueryData(['experimental-features', 'file'], { features: { 'experimental.style_dna_v2': false, 'experimental.workspace_tools_v2': true } }));
  await waitFor(() => expect(screen.queryByDisplayValue('PRIVATE_DRAFT')).toBeNull()); expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
});

it('a newer module intent suppresses late original navigation reads after explicit discard', async () => {
  const job = deferred<any>(); vi.mocked(api.job).mockImplementation(() => job.promise);
  await openStyle(); click('Open guarded job'); expect(api.job).not.toHaveBeenCalled();
  click('放弃 Style DNA 修改并离开'); await waitFor(() => expect(api.job).toHaveBeenCalledTimes(1));
  click('Switch image'); await screen.findByText('Destination image module');
  await act(async () => job.resolve({ ...taskState('author-two', 'COMPLETED', 'LATE', 10), chapter_id: 'recovery:2' }));
  expect(useStudio.getState().chapterId).toBe('recovery:1'); expect(screen.getByText('Destination image module')).toBeTruthy();
});
it('forbidden save removes private draft and pending transition without navigation', async () => {
  saveResponse = async () => new Response(JSON.stringify({ code: 'FORBIDDEN' }), { status: 403 });
  await openStyle(); click('Open overview'); click('保存 Style DNA 后离开');
  await waitFor(() => expect(screen.queryByDisplayValue('PRIVATE_DRAFT')).toBeNull());
  expect(screen.getByLabelText('Style DNA 档案')).toBeTruthy(); expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
});
it('manuscript protection remains in force after Style DNA is saved', async () => {
  await openStyle(); edit('UNSAVED_MANUSCRIPT'); click('切换本机作品'); click('保存 Style DNA 后离开');
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull());
  expect(useStudio.getState().novelId).toBe('recovery'); expect(editor().value).toBe('UNSAVED_MANUSCRIPT');
});

it('rechecks manuscript changes made while the leave confirmation is pending', async () => {
  await openStyle(); click('切换本机作品'); edit('MANUSCRIPT_AFTER_PROMPT'); click('保存 Style DNA 后离开');
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull());
  expect(useStudio.getState().novelId).toBe('recovery'); expect(editor().value).toBe('MANUSCRIPT_AFTER_PROMPT');
});
it('does not treat an unverified success-shaped receipt as a durable save', async () => {
  saveResponse = async () => new Response(JSON.stringify({ ...profile, id: 'another-style', version: 2 }), { status: 200 });
  await openStyle(); click('Open overview'); click('保存 Style DNA 后离开');
  await screen.findByText(/Style DNA 尚未确认保存/);
  expect(screen.getByDisplayValue('PRIVATE_DRAFT')).toBeTruthy(); expect(screen.getByLabelText('Style DNA 档案')).toBeTruthy();
});

async function openCreativeStyle() {
  setup(true, false, true); click('打开 V2 创作工作台');
  await screen.findByRole('button', { name: '返回经典工作区' });
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  click('Open style tools'); await screen.findByRole('option', { name: /Original/ });
  fireEvent.change(screen.getByLabelText('Style DNA 档案'), { target: { value: 'style' } });
  fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'CREATIVE_PRIVATE_DRAFT' } });
}
it.each(['保存 Style DNA 后离开', '放弃 Style DNA 修改并离开'])('composes the original CreativeWorkspace return with Style DNA cancel and %s', async choice => {
  await openCreativeStyle(); edit('CREATIVE_MANUSCRIPT'); click('返回经典工作区');
  expect(screen.getByRole('region', { name: 'Style DNA 未保存修改' })).toBeTruthy();
  click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('CREATIVE_PRIVATE_DRAFT')).toBeTruthy(); expect(editor().value).toBe('CREATIVE_MANUSCRIPT');
  click('返回经典工作区'); click(choice);
  await waitFor(() => expect(screen.queryByRole('button', { name: '返回经典工作区' })).toBeNull());
  expect(screen.queryByDisplayValue('CREATIVE_PRIVATE_DRAFT')).toBeNull(); expect(editor().value).toBe('CREATIVE_MANUSCRIPT');
  const writes = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'PUT');
  expect(writes).toHaveLength(choice.startsWith('保存') ? 1 : 0);
});
it('quarantines a batched store A/B/A editor and protects fresh edits after retirement', async () => {
  await openStyle(); click('Open overview');
  act(() => { useStudio.setState({ novelId: 'other' }); useStudio.setState({ novelId: 'recovery' }); });
  expect(screen.queryByDisplayValue('PRIVATE_DRAFT')).toBeNull(); expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
  await screen.findByLabelText('Style DNA 标题'); fireEvent.change(screen.getByLabelText('Style DNA 标题'), { target: { value: 'FRESH_DRAFT' } });
  click('Open overview'); expect(screen.getByRole('region', { name: 'Style DNA 未保存修改' })).toBeTruthy();
  click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('FRESH_DRAFT')).toBeTruthy();
});

it('keeps Style DNA confirmation reachable after switching to another creative mode', async () => {
  await openCreativeStyle(); fireEvent.click(screen.getByRole('tab', { name: /Screenplay/ }));
  await screen.findByLabelText('文档标题');
  fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'CREATIVE_DOCUMENT_DRAFT' } });
  click('返回经典工作区');
  expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
  fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); click('确认离开');
  expect(screen.getByRole('region', { name: 'Style DNA 未保存修改' })).toBeTruthy();
  click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('CREATIVE_DOCUMENT_DRAFT')).toBeTruthy(); fireEvent.click(screen.getByRole('tab', { name: /Novel/ }));
  expect(screen.getByDisplayValue('CREATIVE_PRIVATE_DRAFT')).toBeTruthy();
});

it.each([['保存 Style DNA 后离开', '返回经典工作区'], ['放弃 Style DNA 修改并离开', '返回经典工作区'], ['保存 Style DNA 后离开', 'Switch image'], ['放弃 Style DNA 修改并离开', 'Switch image']])('rechecks creative edits during %s before %s', async (choice, destination) => {
  const saving = deferred<Response>(); saveResponse = () => saving.promise;
  await openCreativeStyle(); fireEvent.click(screen.getByRole('tab', { name: /Screenplay/ }));
  await screen.findByLabelText('文档标题');
  fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'APPROVED_OLD_CREATIVE' } });
  click(destination); fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); click('确认离开');
  if (choice.startsWith('保存')) click(choice);
  fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'NEW_CREATIVE_AFTER_APPROVAL' } });
  if (choice.startsWith('保存')) await act(async () => saving.resolve(new Response(JSON.stringify({ ...profile, version: 2 }), { status: 200 })));
  else click(choice);
  await screen.findByText('创作草稿或操作状态已改变，未离开。请重新选择离开并核对当前输入。');
  expect(screen.getByDisplayValue('NEW_CREATIVE_AFTER_APPROVAL')).toBeTruthy(); expect(screen.getByRole('button', { name: '返回经典工作区' })).toBeTruthy();
  // A new explicit confirmation covers the new creative input. The Style
  // decision is already complete, so this does not trigger a second Style save.
  click(destination); fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); click('确认离开');
  await waitFor(() => expect(screen.queryByRole('button', { name: '返回经典工作区' })).toBeNull());
  expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(choice.startsWith('保存') ? 1 : 0);
});
