// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LocalTutorDialog, useLocalTutorIntegration, type LocalTutorProps } from './LocalTutorIntegration';
import { diagnosticFields } from './client';

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
    if (path === '/status') return response({ feature_enabled: true, enabled, acceptance_mode: false, product, capabilities, disabled_capabilities: ['model.execute', 'project.write'], desktop_status: 'LOCAL_REQUIRED', ...overrideStatus });
    if (path === '/settings') { enabled = body.enabled; return response({ enabled }); }
    if (path === '/connect') return response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'session', product, capabilities, desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY' });
    if (path === '/context/preview') return response({ request_id: body.request_id, session_id: body.session_id, preview_id: 'preview', capsule: capsule(body.content_kind === 'SELECTION' ? 'SELECTED_TEXT' : body.content_kind === 'CHAPTER' ? 'CURRENT_CHAPTER' : 'NONE'), expires_at: expires() });
    if (path.startsWith('/context/sources')) return response({ session_id: 'session', items: [{ id: 'source-chapter', label: 'Chapter 2', version: 3 }] });
    if (path === '/diagnostics/preview') return response({ request_id: body.request_id, session_id: body.session_id, preview_id: 'diagnostic-preview', diagnostic: Object.fromEntries(body.fields.map((field: string) => [field, `safe-${field}`])), capsule: { ...capsule(), module: 'local-interop', surface: 'diagnostics', chapter_id: undefined, chapter_version: undefined }, expires_at: expires() });
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
  await act(async () => resolve(response({ request_id: body.request_id, session_id: 'late-session', product, capabilities, mode: 'MOCK_ONLY' })));
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
  expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(trigger);
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
  handler = (path, body) => path === '/connect' ? response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'wire-session', product, capabilities, desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY' })
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
  handler = (path, body) => path === '/connect' ? response({ request_id: body.request_id, session_id: 'session', protocol_session_id: 'session', product, capabilities: ['tutor.guidance.request', 'tutor.guidance.receive'], desktop_status: 'LOCAL_REQUIRED', mode: 'MOCK_ONLY' }) : undefined;
  render(<LocalTutorDialog {...props()} onClose={vi.fn()} />); await connect();
  expect((screen.getByRole('checkbox', { name: '选中文本' }) as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByRole('checkbox', { name: '当前章节' }) as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '共享诊断' }));
  expect((screen.getByRole('button', { name: '生成诊断预览' }) as HTMLButtonElement).disabled).toBe(true);
});
