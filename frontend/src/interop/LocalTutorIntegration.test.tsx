// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LocalTutorDialog, useLocalTutorIntegration, type LocalTutorProps } from './LocalTutorIntegration';
import { diagnosticFields } from './client';
import { desktopFixture } from '../../tests/fixtures/desktopInterop';
import { permissionIds, permissionLabels } from './desktop';

const scope = { workspaceId: 'workspace', projectId: 'project', storylineId: 'storyline', branchId: 'branch' };
const context = { sessionToken: 'private-session-header-only', actor: { id: 'author', displayName: 'Author', workspaceId: 'workspace' }, scope };
const capabilities = ['project.context.read', 'project.selection.share', 'project.metadata.read', 'task.status.read', 'task.error.read', 'diagnostics.read', 'model.registry.read', 'model.runtime.status.read', 'tutor.guidance.request', 'tutor.guidance.receive', 'verifier.request', 'verifier.result.receive', 'handoff.open_feature'];
const protocol = { protocol_name: 'PoemSeed Local Interop', protocol_version: '1.0' };
const product = { ...protocol, product_id: 'poemseed.tutor.desktop', display_name: 'Synthetic Tutor', product_version: '0.1.0', instance_id: 'tutor-instance', product_role: 'AI_TUTOR', protocol_versions: ['1.0'], capabilities };
const expires = () => new Date(Date.now() + 60_000).toISOString();
const capsule = (level = 'NONE') => ({ ...protocol, capsule_id: 'capsule', source_version: '7', capsule_hash: 'a'.repeat(64), product_id: 'poemseed.creative.studio', product_version: '0.7.0', instance_id: 'studio-instance', module: 'NOVEL', surface: 'editor', chapter_id: 'chapter', chapter_version: 7, privacy_scope: 'LOCAL_ONLY', content: level === 'NONE' ? { level: 'NONE' } : { level, text: '选区😀', consent_id: 'consent' }, created_at: new Date().toISOString(), expires_at: expires(), evidence: [] });
const advice = (request_id: string, session_id = 'session') => ({ ...protocol, request_id, session_id, guidance_id: 'guidance', summary: '先核对运行时', diagnosis: '只读分析', steps: [{ step_id: 'step', instruction: '打开模型中心查看状态', handoff: { ...protocol, action: 'OPEN_FEATURE', target_product_id: 'poemseed.creative.studio', feature: 'model-center' } }], warnings: ['不要共享凭据'], references: [{ source_id: 'source', label: '真实运行状态', locator: 'javascript:alert(1)' }], verification_condition: { field: 'runtime_status', operator: 'EQ', expected_value: 'READY', source_id: 'source' }, created_at: new Date().toISOString(), privacy_scope: 'LOCAL_ONLY' });
const props = (): LocalTutorProps => ({ context, projectId: 'project', module: 'NOVEL', surface: 'editor', chapterId: 'chapter', chapterVersion: 7, sourceReady: true, selection: { from: 8, to: 12, text: '选区😀', text_start: 5, text_end: 8 }, onNavigate: vi.fn() });
let enabled: boolean;
let overrideStatus: Record<string, unknown>;
let handler: ((path: string, body: any, init: RequestInit) => Promise<Response> | Response | undefined) | undefined;
let calls: { path: string; body: any; init: RequestInit }[];
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => {
  enabled = true; overrideStatus = {}; calls = []; handler = undefined;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const path = String(url).replace('/api/local-interop', ''), body = init.body ? JSON.parse(String(init.body)) : {};
    calls.push({ path, body, init });
    const custom = handler?.(path, body, init); if (custom) return custom;
    if (path === '/status' || path.startsWith('/status?')) return response({ feature_enabled: true, enabled, acceptance_mode: false, product, capabilities, disabled_capabilities: ['model.execute', 'project.write'], desktop_status: 'LOCAL_REQUIRED', ...overrideStatus });
    if (path === '/settings') { enabled = body.enabled; return response({ enabled }); }
    if (path === '/connect') return response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'session', product, capabilities, desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY', subscription_active: false, metadata_fields: [] });
    if (path === '/context/preview') return response({ request_id: body.request_id, session_id: body.session_id, preview_id: 'preview', capsule: capsule(body.content_kind === 'SELECTION' ? 'SELECTED_TEXT' : body.content_kind === 'CHAPTER' ? 'CURRENT_CHAPTER' : 'NONE'), expires_at: expires() });
    if (path.startsWith('/context/sources')) return response({ session_id: 'session', items: [{ id: 'source-chapter', label: 'Chapter 2', version: 3 }] });
    if (path === '/diagnostics/preview') return response({ request_id: body.request_id, session_id: body.session_id, preview_id: 'diagnostic-preview', diagnostic: Object.fromEntries(body.fields.map((field: string) => [field, `safe-${field}`])), capsule: { ...capsule(), module: 'local-interop', surface: 'diagnostics', chapter_id: undefined, chapter_version: undefined }, expires_at: expires(), event_subscription_paused: true });
    if (path === '/disconnect') return response({ session_id: body.session_id, status: 'DISCONNECTED' });
    if (path === '/events/preview') return response({ request_id: body.request_id, session_id: body.session_id, preview_id: 'event-preview', capsule: capsule(), metadata_fields: body.metadata_fields, expires_at: expires(), subscription_active: false });
    if (path === '/events/subscribe') return response({ request_id: body.request_id, session_id: body.session_id, subscription_active: true, metadata_fields: calls.filter(value => value.path === '/events/preview').at(-1)?.body.metadata_fields ?? [] });
    if (path === '/events/unsubscribe') return response({ request_id: body.request_id, session_id: body.session_id, subscription_active: false, metadata_fields: [] });
    if (path === '/ask' || path === '/diagnostics/share') return response({ request_id: body.request_id, session_id: body.session_id, guidance: advice(body.request_id) });
    if (path === '/handoff') return response({ request_id: body.request_id, session_id: body.session_id, route: { action: 'OPEN_FEATURE', feature: 'model-center', project_id: 'project' } });
    if (path === '/verify') return response({ request_id: body.request_id, session_id: body.session_id, result: { ...protocol, request_id: body.request_id, session_id: body.session_id, result_id: 'result', status: 'UNKNOWN', reason: '缺少真实来源', evidence: [], created_at: new Date().toISOString() } });
    return response({ ok: true });
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
async function connect() {
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  fireEvent.change(screen.getByRole('textbox', { name: '开发用本机 Tutor 地址' }), { target: { value: 'http://127.0.0.1:8123' } });
  fireEvent.click(screen.getByRole('button', { name: '连接本机 Tutor' }));
  await screen.findByText('Synthetic Tutor');
}
async function preview() {
  fireEvent.click(screen.getByRole('button', { name: '生成共享预览' }));
  await screen.findByLabelText('待确认的 Context Capsule');
}
async function ask() {
  await preview(); fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' })); await screen.findByText('先核对运行时');
}
function Harness(input: LocalTutorProps) { const ui = useLocalTutorIntegration(input); return <>{ui.entry}{ui.settings}{ui.dialog}<p>Studio 仍然可用</p></>; }

it('does not discover, load context or connect at Studio startup', async () => {
  render(<Harness {...props()} />); expect(calls).toEqual([]);
  fireEvent.click(screen.getByRole('button', { name: '问助手' }));
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  expect(calls.map(value => value.path)).toEqual(['/status']);
});
it('shows default OFF and requires explicit enable before connecting', async () => {
  enabled = false; render(<LocalTutorDialog {...props()} onClose={vi.fn()} />);
  const toggle = await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  expect((toggle as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole('button', { name: '连接本机 Tutor' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(toggle); await waitFor(() => expect((toggle as HTMLInputElement).checked).toBe(true));
  expect(calls.filter(value => value.path === '/settings')).toHaveLength(1);
  expect(calls.some(value => value.path === '/connect')).toBe(false);
});
it('forces acceptance mode OFF and disables the rollout-disabled switch', async () => {
  overrideStatus = { acceptance_mode: true, enabled: true };
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />);
  const toggle = await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' }) as HTMLInputElement;
  expect(toggle.checked).toBe(false); expect(toggle.disabled).toBe(true);
  expect(screen.getByText('V1 Acceptance Mode 强制关闭此实验功能。')).toBeTruthy();
  expect(calls.map(value => value.path)).toEqual(['/status']);
});
it('does not invent permissions for file-only mode', async () => {
  render(<LocalTutorDialog {...props()} context={{ sessionToken: '' }} onClose={vi.fn()} />);
  await screen.findByText('需已授权的工作区会话；当前文件模式仍可正常写作。');
  expect(screen.queryByRole('button', { name: '连接本机 Tutor' })).toBeNull();
  expect(calls).toEqual([]);
});
it('defaults content unchecked, previews metadata only and sends only after confirmation', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  for (const name of ['选中文本', '当前章节', '其他资料（明确选择章节）']) expect((screen.getByRole('checkbox', { name }) as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole('checkbox', { name: '当前任务状态' }) as HTMLInputElement).checked).toBe(true);
  await preview();
  const request = calls.find(value => value.path === '/context/preview')!;
  expect(request.body.content_kind).toBe('NONE'); expect(request.body.expected_chapter_version).toBeUndefined();
  expect(JSON.stringify(request.body)).not.toContain('选区'); expect(calls.some(value => value.path === '/ask')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' })); await screen.findByText('先核对运行时');
  expect(calls.find(value => value.path === '/ask')?.body).toMatchObject({ session_id: 'session', preview_id: 'preview', confirmed: true });
});
it('shares exact current-editor codepoint offsets and version only after opt-in', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('checkbox', { name: '选中文本' }));
  expect(screen.getByLabelText('当前编辑器选区').textContent).toBe('选区😀'); await preview();
  expect(calls.find(value => value.path === '/context/preview')?.body).toMatchObject({ content_kind: 'SELECTION', selection_start: 5, selection_end: 8, expected_chapter_version: 7 });
  expect(calls.some(value => value.path.includes('/api/chapters'))).toBe(false);
});
it('allows only explicitly chosen bounded additional chapters, no automatic project content fetch', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('checkbox', { name: '其他资料（明确选择章节）' }));
  expect((screen.getByRole('button', { name: '生成共享预览' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '列出可选章节元数据' }));
  const chapter = await screen.findByRole('checkbox', { name: 'Chapter 2 · v3' });
  expect((chapter as HTMLInputElement).checked).toBe(false); fireEvent.click(chapter); await preview();
  expect(calls.find(value => value.path === '/context/preview')?.body.context_ids).toEqual(['source-chapter']);
});
it('invalidates preview when metadata selection changes and keeps source choices mutually exclusive', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('checkbox', { name: '选中文本' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '当前章节' }));
  expect((screen.getByRole('checkbox', { name: '选中文本' }) as HTMLInputElement).checked).toBe(false);
  await preview(); fireEvent.click(screen.getByRole('checkbox', { name: '错误代码' }));
  expect(screen.queryByRole('button', { name: '确认并发送给 Tutor' })).toBeNull(); await preview();
  expect(calls.filter(value => value.path === '/context/preview').at(-1)?.body.metadata_fields).not.toContain('error');
});
it('removes diagnostic fields and previews every outgoing context envelope before sharing', async () => {
  render(<LocalTutorDialog {...props()} initialView="diagnostics" onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('checkbox', { name: '错误代码' }));
  fireEvent.click(screen.getByRole('button', { name: '生成诊断预览' }));
  const preview = await screen.findByLabelText('待确认的 Diagnostic Capsule');
  expect(preview.textContent).toContain('context'); expect(preview.textContent).toContain('local-interop');
  expect(preview.textContent).not.toContain('safe-error_code');
  expect(calls.find(value => value.path === '/diagnostics/preview')?.body.fields).toEqual(diagnosticFields.filter(field => field !== 'error_code'));
  expect(calls.some(value => value.path === '/diagnostics/share')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' })); await screen.findByText('先核对运行时');
});
it('renders read-only guidance, inert references and requires explicit host-authorized handoff', async () => {
  const input = props(); render(<LocalTutorDialog {...input} onClose={vi.fn()} />); await connect(); await ask();
  expect(screen.getByText('不要共享凭据')).toBeTruthy(); expect(screen.queryByRole('link')).toBeNull();
  expect(input.onNavigate).not.toHaveBeenCalled(); expect(calls.some(value => value.path === '/handoff')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '核对并打开目标' }));
  await waitFor(() => expect(input.onNavigate).toHaveBeenCalled());
  expect(calls.find(value => value.path === '/handoff')?.body.explicit_click).toBe(true);
  expect(calls.every(value => !/execute|accept|saveChapter|settings/.test(value.path))).toBe(true);
});
it('verifies only after a click and shows UNKNOWN instead of treating advice as success', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await ask();
  expect(calls.some(value => value.path === '/verify')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '使用当前 Studio 证据验证' }));
  await screen.findByText('UNKNOWN'); expect(screen.queryByText('VERIFIED')).toBeNull();
});
it('cancels pending connects by request identity and disconnects a late-created session', async () => {
  let resolve!: (response: Response) => void; let body: any;
  handler = (path, value) => path === '/connect' ? (body = value, new Promise<Response>(done => { resolve = done; })) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />);
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  fireEvent.change(screen.getByRole('textbox', { name: '开发用本机 Tutor 地址' }), { target: { value: 'http://127.0.0.1:8123' } });
  fireEvent.click(screen.getByRole('button', { name: '连接本机 Tutor' }));
  fireEvent.click(await screen.findByRole('button', { name: '取消当前请求' }));
  expect(calls.find(value => value.path === '/cancel')?.body.request_id).toBe(body.request_id);
  await act(async () => resolve(response({ request_id: body.request_id, session_id: 'late-session', product, capabilities, mode: 'MOCK_ONLY', subscription_active: false, metadata_fields: [] })));
  await waitFor(() => expect(calls.some(value => value.path === '/disconnect' && value.body.session_id === 'late-session')).toBe(true));
  expect(screen.queryByText('Synthetic Tutor')).toBeNull();
});
it('cancels old responses and prevents duplicate sends during repeated clicks', async () => {
  let resolve!: (response: Response) => void; let requestId = '';
  handler = (path, value) => path === '/ask' ? (requestId = value.request_id, new Promise<Response>(done => { resolve = done; })) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await preview();
  const confirm = screen.getByRole('button', { name: '确认并发送给 Tutor' }); fireEvent.click(confirm); fireEvent.click(confirm);
  expect(calls.filter(value => value.path === '/ask')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: '取消当前请求' }));
  await act(async () => resolve(response({ request_id: requestId, session_id: 'session', guidance: advice(requestId) })));
  expect(screen.queryByText('先核对运行时')).toBeNull();
  expect(calls.find(value => value.path === '/ask')?.init.signal?.aborted).toBe(true);
});
it('closing disconnects the session, restores focus, and clears opt-in on reopen', async () => {
  render(<Harness {...props()} />); const trigger = screen.getByRole('button', { name: '问助手' }); trigger.focus(); fireEvent.click(trigger);
  await connect(); fireEvent.click(screen.getByRole('checkbox', { name: '选中文本' }));
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull()); expect(document.activeElement).toBe(trigger);
  expect(calls.some(value => value.path === '/disconnect')).toBe(true);
  fireEvent.click(trigger); await screen.findByRole('checkbox', { name: '选中文本' });
  expect((screen.getByRole('checkbox', { name: '选中文本' }) as HTMLInputElement).checked).toBe(false);
});
it.each(['project', 'chapter', 'session', 'feature'])('closes and isolates all pending work when %s changes', async kind => {
  const input = props(), view = render(<Harness {...input} />);
  fireEvent.click(screen.getByRole('button', { name: '问助手' })); await connect(); await preview();
  const next = { ...input, ...(kind === 'project' ? { projectId: 'other' } : kind === 'chapter' ? { chapterId: 'other' } : kind === 'feature' ? { surface: 'world' } : { context: { ...context, sessionToken: 'new-session' } }) };
  view.rerender(<Harness {...next} />); expect(screen.queryByRole('dialog')).toBeNull();
  expect(calls.some(value => value.path === '/disconnect')).toBe(true);
});
it('invalidates approval after chapter version or unsaved draft changes', async () => {
  const input = props(), view = render(<LocalTutorDialog {...input} onClose={vi.fn()} />); await connect(); await preview();
  view.rerender(<LocalTutorDialog {...input} chapterVersion={8} sourceReady={false} onClose={vi.fn()} />);
  expect(screen.queryByRole('button', { name: '确认并发送给 Tutor' })).toBeNull();
  expect((screen.getByRole('checkbox', { name: '当前章节' }) as HTMLInputElement).disabled).toBe(true);
  expect(calls.some(value => value.path === '/ask')).toBe(false);
});
it('displays unavailable Tutor safely without exposing arbitrary remote messages', async () => {
  handler = path => path === '/connect' ? response({ detail: { code: 'TUTOR_UNAVAILABLE', message: '/private/path secret<script>bad</script>' } }, 503) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />);
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  fireEvent.change(screen.getByRole('textbox', { name: '开发用本机 Tutor 地址' }), { target: { value: 'http://127.0.0.1:8123' } });
  fireEvent.click(screen.getByRole('button', { name: '连接本机 Tutor' }));
  await screen.findByText('Tutor 当前不可用，Studio 可继续正常使用。');
  expect(document.body.textContent).not.toContain('/private/path');
});
it('rejects stale session receipts and does not use delayed guidance from another session', async () => {
  handler = (path, body) => path === '/ask' ? response({ request_id: body.request_id, session_id: 'wrong-session', guidance: advice(body.request_id, 'wrong-session') }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await preview();
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' }));
  await screen.findByText('预览已过期或来源已变化，请重新预览。'); expect(screen.queryByText('先核对运行时')).toBeNull();
});
it('keeps keyboard focus contained in the dialog', async () => {
  render(<Harness {...props()} />); fireEvent.click(screen.getByRole('button', { name: '问助手' }));
  const modal = await screen.findByRole('dialog'); const close = within(modal).getByRole('button', { name: '关闭本机 Tutor' });
  close.focus(); fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
  expect(document.activeElement).toBe(within(modal).getByRole('button', { name: '关闭并断开' }));
});

it('disables the bridge immediately during a pending request and suppresses its late response', async () => {
  let resolve!: (response: Response) => void; let requestId = '';
  handler = (path, value) => path === '/ask' ? (requestId = value.request_id, new Promise<Response>(done => { resolve = done; })) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await preview();
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' }));
  const toggle = screen.getByRole('checkbox', { name: 'Enable Local Tutor Integration' }) as HTMLInputElement;
  expect(toggle.disabled).toBe(false); fireEvent.click(toggle);
  await waitFor(() => expect(toggle.checked).toBe(false));
  await act(async () => resolve(response({ request_id: requestId, session_id: 'session', guidance: advice(requestId) })));
  expect(screen.queryByText('先核对运行时')).toBeNull();
  expect(calls.some(value => value.path === '/disconnect')).toBe(true);
  expect(calls.some(value => value.path === '/settings' && value.body.enabled === false)).toBe(true);
});
it('preserves separate host authorization and peer protocol session identities', async () => {
  handler = (path, body) => path === '/connect' ? response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'wire-session', product, capabilities, desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY', subscription_active: false, metadata_fields: [] })
    : path === '/ask' ? response({ request_id: body.request_id, session_id: 'session', guidance: advice(body.request_id, 'wire-session') }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await ask();
  expect(screen.getByText('先核对运行时')).toBeTruthy();
});
it('does not send an expired preview', async () => {
  let expiry = expires();
  handler = (path, body) => path === '/context/preview' ? response({ request_id: body.request_id, session_id: body.session_id, preview_id: 'preview', capsule: capsule(), expires_at: expiry }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await preview();
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse(expiry) + 1);
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' }));
  await screen.findByText('预览已过期或来源已变化，请重新预览。');
  expect(calls.some(value => value.path === '/ask')).toBe(false);
});
it('keeps capabilities fail-closed when selection or diagnostic permissions are absent', async () => {
  handler = (path, body) => path === '/connect' ? response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'session', product, capabilities: ['tutor.guidance.request', 'tutor.guidance.receive'], desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY', subscription_active: false, metadata_fields: [] }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  expect((screen.getByRole('checkbox', { name: '选中文本' }) as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByRole('checkbox', { name: '当前章节' }) as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '共享诊断' }));
  expect((screen.getByRole('button', { name: '生成诊断预览' }) as HTMLButtonElement).disabled).toBe(true);
});

async function previewOngoing() {
  fireEvent.click(screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }));
  fireEvent.click(screen.getByRole('button', { name: '预览持续状态共享' }));
  await screen.findByLabelText('持续状态共享预览');
}
async function authorizeOngoing() {
  await previewOngoing(); fireEvent.click(screen.getByRole('button', { name: '确认开启本次会话持续共享' }));
  await screen.findByLabelText('正在共享的状态类别');
}
it('connect and one-shot Ask leave ongoing events OFF until a separate preview and confirmation', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  expect((screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }) as HTMLInputElement).checked).toBe(false);
  expect(screen.getByText('持续共享关闭')).toBeTruthy();
  await ask(); expect(calls.some(value => value.path.startsWith('/events/'))).toBe(false);
  await previewOngoing(); expect(calls.some(value => value.path === '/events/subscribe')).toBe(false);
  const reviewed = JSON.parse(screen.getByLabelText('持续状态共享预览').textContent!);
  expect(reviewed.capsule.content.level).toBe('NONE'); expect(reviewed.metadata_fields).toEqual(['task', 'error', 'model', 'runtime']);
  fireEvent.click(screen.getByRole('button', { name: '确认开启本次会话持续共享' }));
  await screen.findByLabelText('正在共享的状态类别');
  expect(calls.find(value => value.path === '/events/subscribe')?.body).toMatchObject({ session_id: 'session', preview_id: 'event-preview', confirmed: true });
});
it('previews exact chosen ongoing fields and displays the acknowledged allowlist', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '持续共享：当前模型元数据' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '持续共享：错误代码' }));
  fireEvent.click(screen.getByRole('button', { name: '预览持续状态共享' }));
  const preview = await screen.findByLabelText('持续状态共享预览');
  expect(JSON.parse(preview.textContent!).metadata_fields).toEqual(['task', 'runtime']);
  fireEvent.click(screen.getByRole('button', { name: '确认开启本次会话持续共享' }));
  const active = await screen.findByLabelText('正在共享的状态类别');
  expect(active.textContent).toContain('当前任务状态'); expect(active.textContent).toContain('当前模型运行状态');
  expect(active.textContent).not.toContain('错误代码'); expect(active.textContent).not.toContain('当前模型元数据');
});
it('explicit stop clears grant and queued events without silently resuming', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  fireEvent.click(screen.getByRole('button', { name: '停止持续状态共享' }));
  await screen.findByText('持续共享关闭');
  expect(calls.some(value => value.path === '/events/unsubscribe')).toBe(true);
  expect((screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }) as HTMLInputElement).checked).toBe(false);
  await ask(); expect(calls.filter(value => value.path === '/events/subscribe')).toHaveLength(1);
});
it('diagnostic preview pauses ongoing sharing before omissions and never resumes it after sending', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  fireEvent.click(screen.getByRole('button', { name: '共享诊断' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '软件 ID' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '当前功能' }));
  fireEvent.click(screen.getByRole('button', { name: '生成诊断预览' }));
  const preview = await screen.findByLabelText('待确认的 Diagnostic Capsule');
  expect(preview.textContent).not.toContain('safe-software_id'); expect(preview.textContent).not.toContain('safe-feature');
  expect(screen.getByText('持续共享关闭')).toBeTruthy();
  expect(screen.getByText('已停止持续状态共享，再生成最小化诊断预览；不会自动恢复。已发送的信息无法撤回。')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' })); await screen.findByText('先核对运行时');
  expect(calls.filter(value => value.path === '/events/subscribe')).toHaveLength(1);
  expect((screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }) as HTMLInputElement).checked).toBe(false);
});
it('cancelling an uncertain subscribe explicitly revokes it and ignores a late success', async () => {
  let finish!: (response: Response) => void; let requestId = '';
  handler = (path, body) => path === '/events/subscribe' ? (requestId = body.request_id, new Promise<Response>(resolve => { finish = resolve; })) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await previewOngoing();
  fireEvent.click(screen.getByRole('button', { name: '确认开启本次会话持续共享' }));
  fireEvent.click(screen.getByRole('button', { name: '取消当前请求' }));
  await screen.findByText('持续共享关闭');
  expect(calls.some(value => value.path === '/events/unsubscribe')).toBe(true);
  await act(async () => finish(response({ request_id: requestId, session_id: 'session', subscription_active: true, metadata_fields: ['task', 'error', 'model', 'runtime'] })));
  expect(screen.queryByLabelText('正在共享的状态类别')).toBeNull();
  expect(screen.getByText('持续共享关闭')).toBeTruthy();
});
it('does not claim a failed stop succeeded and permits an explicit retry', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  handler = path => path === '/events/unsubscribe' ? response({ code: 'TRANSPORT_ERROR' }, 503) : undefined;
  fireEvent.click(screen.getByRole('button', { name: '停止持续状态共享' }));
  await screen.findByRole('alert'); expect(screen.getByText('状态待确认')).toBeTruthy();
  expect(screen.queryByText('持续共享关闭')).toBeNull();
  handler = undefined; fireEvent.click(screen.getByRole('button', { name: '停止持续状态共享' })); await screen.findByText('持续共享关闭');
});
it('changing source version invalidates a standing grant and requires new consent', async () => {
  const input = props(), view = render(<LocalTutorDialog {...input} onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  view.rerender(<LocalTutorDialog {...input} chapterVersion={8} onClose={vi.fn()} />);
  await screen.findByText('持续共享关闭'); expect(calls.some(value => value.path === '/events/unsubscribe')).toBe(true);
  expect((screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }) as HTMLInputElement).checked).toBe(false);
});
it('rejects a host grant broader than the reviewed fields and revokes that grant', async () => {
  handler = (path, body) => path === '/events/subscribe' ? response({ request_id: body.request_id, session_id: body.session_id, subscription_active: true, metadata_fields: ['task', 'error', 'model', 'runtime', 'unknown'] }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await previewOngoing();
  fireEvent.click(screen.getByRole('button', { name: '确认开启本次会话持续共享' }));
  await screen.findByRole('alert'); await screen.findByText('持续共享关闭');
  expect(calls.some(value => value.path === '/events/unsubscribe')).toBe(true);
  expect(screen.queryByLabelText('正在共享的状态类别')).toBeNull();
});
it('reconnect leaves ongoing sharing unchecked even after a previously active grant', async () => {
  render(<Harness {...props()} />); fireEvent.click(screen.getByRole('button', { name: '问助手' })); await connect(); await authorizeOngoing();
  fireEvent.click(screen.getByRole('button', { name: '关闭并断开' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: '问助手' })); await connect();
  expect(screen.getByText('持续共享关闭')).toBeTruthy();
  expect((screen.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）' }) as HTMLInputElement).checked).toBe(false);
  expect(calls.filter(value => value.path === '/events/subscribe')).toHaveLength(1);
});

it('rejects a connection that already granted ongoing sharing without consent', async () => {
  handler = (path, body) => path === '/connect' ? response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'wire-session', product, capabilities, desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY', subscription_active: true, metadata_fields: ['task'] }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />);
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  fireEvent.change(screen.getByRole('textbox', { name: '开发用本机 Tutor 地址' }), { target: { value: 'http://127.0.0.1:8123' } });
  fireEvent.click(screen.getByRole('button', { name: '连接本机 Tutor' })); await screen.findByRole('alert');
  expect(screen.queryByLabelText('正在共享的状态类别')).toBeNull();
  expect(calls.some(value => value.path === '/disconnect' && value.body.session_id === 'session')).toBe(true);
});

it('explicitly cancelling an event preview invalidates its server receipt', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await previewOngoing();
  fireEvent.click(screen.getByRole('button', { name: '取消持续共享预览' }));
  await waitFor(() => expect(calls.some(value => value.path === '/events/unsubscribe')).toBe(true));
  await screen.findByText('持续共享关闭');
  expect(screen.queryByRole('button', { name: '确认开启本次会话持续共享' })).toBeNull();
  expect(calls.some(value => value.path === '/events/subscribe')).toBe(false);
});

it('leaving an unconfirmed event preview invalidates its receipt instead of retaining a hidden grant path', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await previewOngoing();
  fireEvent.click(screen.getByRole('button', { name: '共享诊断' }));
  await waitFor(() => expect(calls.some(value => value.path === '/events/unsubscribe')).toBe(true));
  await screen.findByText('持续共享关闭');
  expect(screen.queryByRole('button', { name: '确认开启本次会话持续共享' })).toBeNull();
});

it('keeps failed disconnect UNKNOWN with a retry and no false stopped claim', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  handler = path => path === '/disconnect' ? response({ code: 'TRANSPORT_ERROR' }, 503) : undefined;
  fireEvent.click(screen.getByRole('button', { name: '断开连接' }));
  await screen.findByText('连接撤销尚未确认，持续共享可能仍在运行。请重试断开或关闭集成。');
  expect(screen.getAllByText('撤销状态 UNKNOWN').length).toBeGreaterThan(0);
  expect(screen.queryByText('持续共享关闭')).toBeNull();
  expect((screen.getByRole('button', { name: '连接本机 Tutor' }) as HTMLButtonElement).disabled).toBe(true);
  handler = undefined; fireEvent.click(screen.getByRole('button', { name: '重试断开连接' }));
  await screen.findByText('已确认连接撤销；再次共享需要重新连接和确认。');
  expect(screen.queryAllByText('撤销状态 UNKNOWN')).toHaveLength(0);
});
it.each([{ session_id: 'wrong', status: 'DISCONNECTED' }, { session_id: 'session', status: 'PENDING' }, {}])('does not accept an ambiguous disconnect receipt %j', async receipt => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  handler = path => path === '/disconnect' ? response(receipt) : undefined;
  fireEvent.click(screen.getByRole('button', { name: '断开连接' }));
  await screen.findByText('连接撤销尚未确认，持续共享可能仍在运行。请重试断开或关闭集成。');
  expect(screen.queryByText('持续共享关闭')).toBeNull();
  expect(screen.getAllByText('撤销状态 UNKNOWN').length).toBeGreaterThan(0);
});
it('master OFF failure remains UNKNOWN and checked until an acknowledged retry resolves it', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  handler = path => path === '/settings' || path === '/disconnect' ? response({ code: 'TRANSPORT_ERROR' }, 503) : undefined;
  const toggle = screen.getByRole('checkbox', { name: 'Enable Local Tutor Integration' }) as HTMLInputElement;
  fireEvent.click(toggle); await screen.findByRole('button', { name: '重试关闭集成' });
  await waitFor(() => expect((screen.getByRole('button', { name: '重试关闭集成' }) as HTMLButtonElement).disabled).toBe(false));
  expect(toggle.checked).toBe(true); expect(screen.getAllByText('撤销状态 UNKNOWN').length).toBeGreaterThan(0);
  expect(screen.queryByText('持续共享关闭')).toBeNull();
  handler = undefined; fireEvent.click(screen.getByRole('button', { name: '重试关闭集成' }));
  await waitFor(() => expect(toggle.checked).toBe(false));
  expect(screen.queryAllByText('撤销状态 UNKNOWN')).toHaveLength(0);
});
it('a disconnect acknowledgment alone does not claim master OFF succeeded', async () => {
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  handler = path => path === '/settings' ? response({ code: 'TRANSPORT_ERROR' }, 503) : undefined;
  fireEvent.click(screen.getByRole('checkbox', { name: 'Enable Local Tutor Integration' }));
  await screen.findByRole('alert');
  expect((screen.getByRole('checkbox', { name: 'Enable Local Tutor Integration' }) as HTMLInputElement).checked).toBe(true);
  expect(screen.getAllByText('撤销状态 UNKNOWN').length).toBeGreaterThan(0);
});
it('Close waits for revocation and offers an explicitly unconfirmed panel dismissal on failure', async () => {
  const onClose = vi.fn(); render(<LocalTutorDialog {...props()} onClose={onClose} />); await connect(); await authorizeOngoing();
  handler = path => path === '/disconnect' ? response({ code: 'TRANSPORT_ERROR' }, 503) : undefined;
  fireEvent.click(screen.getByRole('button', { name: '关闭并断开' }));
  await screen.findByText('撤销结果未确认。仅关闭面板不代表持续共享已经停止。');
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '仅关闭面板（撤销未确认）' })); expect(onClose).toHaveBeenCalledOnce();
});
it('does not let a late disconnect failure undo an acknowledged master OFF', async () => {
  let finish!: (response: Response) => void;
  handler = path => path === '/disconnect' ? new Promise<Response>(resolve => { finish = resolve; }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Enable Local Tutor Integration' }));
  await waitFor(() => expect((screen.getByRole('checkbox', { name: 'Enable Local Tutor Integration' }) as HTMLInputElement).checked).toBe(false));
  await act(async () => finish(response({ code: 'TRANSPORT_ERROR' }, 503)));
  expect(screen.queryAllByText('撤销状态 UNKNOWN')).toHaveLength(0);
});

it('Escape closes an unavailable-Tutor dialog after async button focus falls back to body', async () => {
  handler = path => path === '/connect' ? response({ code: 'TUTOR_UNAVAILABLE' }, 503) : undefined;
  render(<Harness {...props()} />);
  const trigger = screen.getByRole('button', { name: '问助手' }); trigger.focus(); fireEvent.click(trigger);
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  fireEvent.change(screen.getByRole('textbox', { name: '开发用本机 Tutor 地址' }), { target: { value: 'http://127.0.0.1:9' } });
  const connectButton = screen.getByRole('button', { name: '连接本机 Tutor' }); connectButton.focus(); fireEvent.click(connectButton);
  await screen.findByRole('alert'); (document.activeElement as HTMLElement).blur();
  expect(document.activeElement).toBe(document.body);
  fireEvent.keyDown(document.body, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(document.activeElement).toBe(trigger);
});

it('Tab returns escaped async focus to the active dialog without reaching the underlying workspace', async () => {
  render(<Harness {...props()} />); fireEvent.click(screen.getByRole('button', { name: '问助手' }));
  await screen.findByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  (document.activeElement as HTMLElement).blur(); expect(document.activeElement).toBe(document.body);
  fireEvent.keyDown(document.body, { key: 'Tab' });
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '关闭本机 Tutor' }));
});


it('connection status comes from the host formal state, not successful HTTP or a peer product ID', async () => {
  overrideStatus.desktop = desktopFixture('UNTRUSTED');
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect();
  await waitFor(() => expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Untrusted'));
  expect(screen.getByText('Peer Authenticated：未确认')).toBeTruthy();
  expect(calls.some(value => value.path === '/status?session_id=session')).toBe(true);
  expect(screen.getByLabelText('权限中心').textContent).not.toContain('GRANTED只');
});
it.each(permissionIds)('independently revokes %s using a correlated host receipt, without revoking other permissions', async permissionId => {
  const snapshot = desktopFixture(); overrideStatus.desktop = snapshot;
  handler = (path, body) => {
    if (path !== '/permissions/revoke') return;
    const next = structuredClone(snapshot);
    next.connections[0].permissions.find(value => value.id === body.permission_id)!.state = 'REVOKED';
    return response({ request_id: body.request_id, session_id: body.session_id, permission_id: body.permission_id, status: 'REVOKED', permissions: next.connections[0].permissions, desktop: next });
  };
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect();
  const button = await screen.findByRole('button', { name: `撤销 ${permissionLabels[permissionId]}` });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(button);
  await screen.findByText('主机已确认撤销此权限；关联预览已清除，旧响应不会用于新请求。');
  const center = screen.getByLabelText('权限中心');
  expect(within(center).getAllByText('REVOKED')).toHaveLength(1);
  expect(within(center).getAllByText('AVAILABLE')).toHaveLength(8);
  expect(calls.find(value => value.path === '/permissions/revoke')?.body).toMatchObject({ session_id: 'session', permission_id: permissionId });
});
it('a stale permission receipt cannot change the current session or claim revocation', async () => {
  overrideStatus.desktop = desktopFixture();
  handler = (path, body) => path === '/permissions/revoke' ? response({ request_id: body.request_id, session_id: 'old-session', permission_id: body.permission_id, status: 'REVOKED', permissions: [], desktop: desktopFixture('AUTHORIZED', 'old-session') }) : undefined;
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect();
  const button = screen.getByRole('button', { name: `撤销 ${permissionLabels.selection}` }); await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(button);
  await screen.findByRole('alert'); expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Unknown');
  expect(screen.queryByText('主机已确认撤销此权限；关联预览已清除，旧响应不会用于新请求。')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '问助手' }));
  expect((screen.getByRole('button', { name: '生成共享预览' }) as HTMLButtonElement).disabled).toBe(true);
});
it.each(['request_id', 'revoked', 'subscriptions_stopped', 'pending_cancelled', 'standing_grants_cleared', 'transport_disconnected'])('emergency disconnect never claims success without %s acknowledgment', async field => {
  overrideStatus.desktop = desktopFixture();
  handler = (path, body) => {
    if (path !== '/disconnect-revoke') return;
    const receipt: Record<string, unknown> = { request_id: body.request_id, session_id: body.session_id, status: 'DISCONNECTED', revoked: true, subscriptions_stopped: true, pending_cancelled: true, standing_grants_cleared: true, transport_disconnected: true };
    delete receipt[field]; return response(receipt);
  };
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('button', { name: 'Disconnect & Revoke' }));
  await screen.findByText('连接撤销尚未确认，持续共享可能仍在运行。请重试断开或关闭集成。');
  expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Unknown');
  expect(screen.queryByText('持续共享关闭')).toBeNull();
  expect((screen.getByRole('button', { name: '连接本机 Tutor' }) as HTMLButtonElement).disabled).toBe(true);
});
it('emergency disconnect cancels the in-flight request and requires the complete acknowledgment before showing success', async () => {
  let finish!: (response: Response) => void; let lateRequest = '';
  overrideStatus.desktop = desktopFixture();
  handler = (path, body) => {
    if (path === '/ask') return new Promise<Response>(resolve => { finish = resolve; lateRequest = body.request_id; });
    if (path === '/disconnect-revoke') return response({ request_id: body.request_id, session_id: body.session_id, status: 'DISCONNECTED', revoked: true, subscriptions_stopped: true, pending_cancelled: true, standing_grants_cleared: true, transport_disconnected: true });
  };
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect(); await preview();
  fireEvent.click(screen.getByRole('button', { name: '确认并发送给 Tutor' }));
  fireEvent.click(screen.getByRole('button', { name: 'Disconnect & Revoke' }));
  await screen.findByText('已确认 Disconnect & Revoke：会话、订阅、待处理请求和持续授权已撤销，Transport 已断开。作品与 Tutor 历史保留。');
  expect(calls.some(value => value.path === '/cancel' && value.body.request_id === lateRequest)).toBe(true);
  await act(async () => finish(response({ request_id: lateRequest, session_id: 'session', guidance: advice(lateRequest) })));
  expect(screen.queryByText('先核对运行时')).toBeNull();
});

it('a revoke receipt cannot broaden another permission or restore an earlier revoked category', async () => {
  const snapshot = desktopFixture(); snapshot.connections[0].permissions.find(value => value.id === 'deep_link')!.state = 'REVOKED'; overrideStatus.desktop = snapshot;
  handler = (path, body) => {
    if (path !== '/permissions/revoke') return;
    const next = desktopFixture(); next.connections[0].permissions.find(value => value.id === body.permission_id)!.state = 'REVOKED';
    return response({ request_id: body.request_id, session_id: body.session_id, permission_id: body.permission_id, status: 'REVOKED', permissions: next.connections[0].permissions, desktop: next });
  };
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect();
  fireEvent.click(screen.getByRole('button', { name: `撤销 ${permissionLabels.selection}` }));
  await screen.findByRole('alert'); expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Unknown');
  expect(screen.queryByText('主机已确认撤销此权限；关联预览已清除，旧响应不会用于新请求。')).toBeNull();
});
it('a failed scoped status refresh cannot substitute another session detail or enable content sharing', async () => {
  overrideStatus.desktop = desktopFixture('AUTHORIZED', 'different-session');
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect();
  await screen.findByRole('alert'); expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Unknown');
  expect(screen.queryByText('Synthetic Tutor · MOCK_ONLY')).toBeNull();
  for (const button of within(screen.getByLabelText('权限中心')).getAllByRole('button')) expect((button as HTMLButtonElement).disabled).toBe(true);
});

it('a late formal status response cannot undo acknowledged emergency revocation', async () => {
  overrideStatus.desktop = desktopFixture();
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect();
  let finish!: (response: Response) => void; let delayed = false;
  handler = (path, body) => {
    if (path === '/status?session_id=session' && !delayed) { delayed = true; return new Promise<Response>(resolve => { finish = resolve; }); }
    if (path === '/disconnect-revoke') {
      overrideStatus.desktop = { ...desktopFixture('DISCONNECTED'), connections: [] };
      return response({ request_id: body.request_id, session_id: body.session_id, status: 'DISCONNECTED', revoked: true, subscriptions_stopped: true, pending_cancelled: true, standing_grants_cleared: true, transport_disconnected: true });
    }
  };
  fireEvent.click(screen.getByRole('button', { name: '刷新主机状态' }));
  await waitFor(() => expect(delayed).toBe(true));
  fireEvent.click(screen.getByRole('button', { name: 'Disconnect & Revoke' }));
  await waitFor(() => expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Disconnected'));
  await act(async () => finish(response({ feature_enabled: true, enabled: true, acceptance_mode: false, product, capabilities, disabled_capabilities: [], desktop_status: 'LOCAL_REQUIRED', desktop: desktopFixture('AUTHORIZED') })));
  expect(screen.getByLabelText('桌面集成状态').textContent).toContain('Disconnected');
  expect(screen.queryByText('Synthetic Tutor · MOCK_ONLY')).toBeNull();
});

it('refresh confirms an out-of-band standing revoke without ever silently restoring a grant', async () => {
  const snapshot = desktopFixture(); overrideStatus.desktop = snapshot;
  handler = (path) => {
    if (path === '/events/subscribe') { snapshot.connections[0].permissions.find(value => value.id === 'standing_metadata_events')!.state = 'GRANTED'; snapshot.connections[0].standing_permissions = ['standing_metadata_events']; }
    return undefined;
  };
  render(<LocalTutorDialog {...props()} initialView="settings" onClose={vi.fn()} />); await connect(); await authorizeOngoing();
  snapshot.connections[0].permissions.find(value => value.id === 'standing_metadata_events')!.state = 'REVOKED'; snapshot.connections[0].standing_permissions = [];
  await waitFor(() => expect((screen.getByRole('button', { name: '刷新主机状态' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '刷新主机状态' })); await screen.findByText('持续共享关闭');
  snapshot.connections[0].permissions.find(value => value.id === 'standing_metadata_events')!.state = 'GRANTED'; snapshot.connections[0].standing_permissions = ['standing_metadata_events'];
  fireEvent.click(screen.getByRole('button', { name: '刷新主机状态' })); await screen.findByText('状态待确认');
  expect(screen.queryByLabelText('正在共享的状态类别')).toBeNull();
  expect(calls.filter(value => value.path === '/events/subscribe')).toHaveLength(1);
});
