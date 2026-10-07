// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { WorkspaceInteractionPanel } from './WorkspaceInteractionPanel';

const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const prefs = { keyboard_enabled: true, shortcuts: { open_search: 'Mod+Shift+F' }, announcements: 'polite', reduced_motion: 'system', confirm_navigation_with_unsaved_input: true };
const profile = { version: 2, preferences: prefs, state: 'READY', recovery_required: false };
const commands = { revision: 'a'.repeat(64), preferences_version: 2, state: 'READY', items: [{ id: 'open_search', section: 'search', label: '搜索与命令', shortcut: 'Mod+Shift+F' }] };
const client = () => experimentalClient('synthetic', { sessionToken: '' });
function backend(extra?: (url: string, init?: RequestInit) => Response | Promise<Response> | undefined) {
  return vi.fn(async (url: string, init?: RequestInit) => extra?.(url, init) || response(url.endsWith('/commands') ? commands : url.endsWith('/history') ? { items: [{ version: 1, state: 'READY' }] } : url.endsWith('/resolve') ? { kind: 'workspace_section', section: 'search', command_id: 'open_search', requires_dirty_guard: true, dispatched: false } : profile));
}
function mount(api = client(), dirty = false, onSection = vi.fn(), currentSection = 'resume') {
  return { onSection, ...render(<StrictMode><section aria-label="工作现场工具"><button>工作现场焦点</button><input aria-label="本地输入" /><div contentEditable aria-label="正文编辑" suppressContentEditableWarning>正文</div><WorkspaceInteractionPanel client={api} dirty={dirty} currentSection={currentSection} onSection={onSection} /></section></StrictMode>) };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('workspace interaction functional surface', () => {
  it('reads actual server preferences without saving or dispatching', async () => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch); mount();
    expect(await screen.findByText('偏好 v2')).toBeTruthy();
    expect((screen.getByLabelText('启用当前工具内的快捷键') as HTMLInputElement).checked).toBe(true);
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });
  it('explicitly saves CAS and cancellation discards only local preferences', async () => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch); mount();
    const control = await screen.findByLabelText('启用当前工具内的快捷键');
    fireEvent.click(control); fireEvent.click(screen.getByText('取消偏好修改'));
    expect((control as HTMLInputElement).checked).toBe(true);
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false);
    fireEvent.click(control); fireEvent.click(screen.getByText('保存操作偏好'));
    await screen.findByText('操作偏好已保存');
    const write = fetch.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(JSON.parse(String(write[1]?.body))).toMatchObject({ expected_version: 2, preferences: { keyboard_enabled: false } });
  });
  it('uses original keyboard contract only within active workspace and resolves revision', async () => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch); const { onSection } = mount();
    await screen.findByText('Mod+Shift+F');
    fireEvent.keyDown(screen.getByText('工作现场焦点'), { key: 'f', ctrlKey: true, shiftKey: true });
    await waitFor(() => expect(onSection).toHaveBeenCalledWith('search'));
    const resolve = fetch.mock.calls.find(([url]) => url.endsWith('/resolve'))!;
    expect(JSON.parse(String(resolve[1]?.body))).toEqual({ command_id: 'open_search', expected_revision: 'a'.repeat(64) });
    expect(fetch.mock.calls.some(([url]) => /execute|generate|cancel/.test(url))).toBe(false);
  });
  it.each(['input', 'contenteditable', 'composition', 'repeat', 'outside', 'alt'])('never captures %s keyboard input', async mode => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch); const { onSection } = mount();
    await screen.findByText('Mod+Shift+F');
    const target = mode === 'input' ? screen.getByLabelText('本地输入') : mode === 'contenteditable' ? screen.getByLabelText('正文编辑') : mode === 'outside' ? document.body : screen.getByText('工作现场焦点');
    fireEvent.keyDown(target, { key: 'f', ctrlKey: true, shiftKey: true, isComposing: mode === 'composition', repeat: mode === 'repeat', altKey: mode === 'alt' });
    expect(onSection).not.toHaveBeenCalled();
    expect(fetch.mock.calls.some(([url]) => url.endsWith('/resolve'))).toBe(false);
  });
  it('requires dirty confirmation and cancellation never resolves a command', async () => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch); const { onSection } = mount(client(), true);
    fireEvent.click(await screen.findByText('搜索与命令命令'));
    expect(screen.getByText('切换工作现场前确认')).toBeTruthy();
    fireEvent.click(screen.getByText('留在当前工具'));
    expect(onSection).not.toHaveBeenCalled();
    expect(fetch.mock.calls.some(([url]) => url.endsWith('/resolve'))).toBe(false);
    fireEvent.click(screen.getByText('搜索与命令命令'));
    fireEvent.click(screen.getByText('继续切换到搜索与命令'));
    await waitFor(() => expect(onSection).toHaveBeenCalledWith('search'));
  });
  it('does not navigate late results after a newer section change', async () => {
    let finish: (value: Response) => void = () => {};
    const fetch = backend(url => url.endsWith('/resolve') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined);
    vi.stubGlobal('fetch', fetch); const api = client(); const { rerender, onSection } = mount(api);
    fireEvent.click(await screen.findByText('搜索与命令命令'));
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/resolve'))).toBe(true));
    rerender(<section aria-label="工作现场工具"><WorkspaceInteractionPanel client={api} dirty={false} currentSection="tasks" onSection={onSection} /></section>);
    await act(async () => finish(response({ kind: 'workspace_section', section: 'search', dispatched: false })));
    expect(onSection).not.toHaveBeenCalled();
  });
  it('exposes conflict without discarding unsaved preference values', async () => {
    vi.stubGlobal('fetch', backend((url, init) => url.endsWith('/interaction') && init?.method === 'PUT' ? response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409) : undefined));
    mount(); const control = await screen.findByLabelText('启用当前工具内的快捷键');
    fireEvent.click(control); fireEvent.click(screen.getByText('保存操作偏好'));
    await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
    expect((control as HTMLInputElement).checked).toBe(false);
    expect((screen.getByText('取消偏好修改') as HTMLButtonElement).disabled).toBe(false);
  });
  it('corruption disables shortcuts and allows explicit recovery', async () => {
    const fetch = backend(url => url.endsWith('/interaction') ? response({ ...profile, recovery_required: true, state: 'RECOVERY_REQUIRED' }) : url.endsWith('/commands') ? response({ ...commands, state: 'RECOVERY_REQUIRED', items: commands.items.map(row => ({ ...row, shortcut: null })) }) : undefined);
    vi.stubGlobal('fetch', fetch); mount();
    await screen.findByText(/偏好记录需要恢复/);
    expect((screen.getByText('搜索与命令命令') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByText('重置操作偏好')); await screen.findByText('操作偏好已重置');
    const call = fetch.mock.calls.find(([url]) => url.endsWith('/reset'))!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({ expected_version: 2 });
  });
});
