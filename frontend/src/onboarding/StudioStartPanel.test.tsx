// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { studioIntentState } from './studioEntryContract';
import { StudioStartPanel } from './StudioStartPanel';
import { STUDIO_INTENT_IDS, type StudioEntryClient, type StudioEntryIntent, type StudioInterfaceMode } from './studioEntryTypes';
import { useStudioEntry, type StudioEntryControllerConfig } from './useStudioEntry';

const rows = [
  { id: 'novel-1', title: '第一个项目', updated_at: null, entry_kind: 'NEUTRAL_STUDIO', genre: null, status: null },
  { id: 'novel-2', title: '第二个项目', updated_at: null, entry_kind: null, genre: null, status: null },
];
const savedIntent = (selected: string[] = []): StudioEntryIntent => studioIntentState({
  version: 1, preset: 'TEXT', editable: true, history_retained: true,
  values: STUDIO_INTENT_IDS.map(intent_id => ({ intent_id, label: intent_id === 'custom' ? '自定义' : intent_id, selected: selected.includes(intent_id), custom: intent_id === 'custom' })),
}, 'novel-1');
function fakeClient(patch: Partial<Record<keyof StudioEntryClient, unknown>> = {}) {
  const client = {
    listProjects: vi.fn(async () => rows),
    createBlankProject: vi.fn(async () => ({ id: 'novel-new', title: '新项目', studio_ready: true, requires_scope_selection: false })),
    readIntent: vi.fn(async () => savedIntent()),
    saveIntent: vi.fn(async () => savedIntent(['image_design'])),
    ...patch,
  };
  return client as unknown as StudioEntryClient;
}
/** The Lead owns the mode and the navigation; this host mirrors that wiring. */
function Host({ client, onOpenProject, config = {} }: {
  client: StudioEntryClient; onOpenProject: (projectId: string) => void;
  config?: Partial<StudioEntryControllerConfig>;
}) {
  const [mode, setMode] = useState<StudioInterfaceMode>('NOVICE');
  const controller = useStudioEntry({ client, identity: 'entry-session', active: true, onOpenProject, ...config });
  return <StudioStartPanel controller={controller} onOpenProject={onOpenProject} mode={mode} onModeChange={setMode} />;
}
const panel = () => screen.getByRole('region', { name: '项目入口' });

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('studio project entry panel', () => {
  it('offers the three clear entries and the project list', async () => {
    const readIntent = vi.fn(async () => savedIntent());
    render(<Host client={fakeClient({ readIntent })} onOpenProject={vi.fn()} />);
    const region = panel();
    expect(within(region).getByRole('region', { name: '继续项目' })).toBeTruthy();
    expect(within(region).getByRole('region', { name: '空白开始' })).toBeTruthy();
    expect(within(region).getByRole('region', { name: '按创作意图开始' })).toBeTruthy();
    await within(region).findByRole('button', { name: /第一个项目/ });
    expect(within(region).getByRole('button', { name: /第二个项目/ })).toBeTruthy();
    expect(readIntent).not.toHaveBeenCalled();
  });

  it('continues a project through the callback after reading its saved intent', async () => {
    const onOpenProject = vi.fn();
    const readIntent = vi.fn(async () => savedIntent(['image_design']));
    render(<Host client={fakeClient({ readIntent })} onOpenProject={onOpenProject} />);
    const region = panel();
    fireEvent.click(await within(region).findByRole('button', { name: /第一个项目/ }));
    await waitFor(() => expect(readIntent).toHaveBeenCalledWith('novel-1', expect.anything()));
    fireEvent.click(await within(region).findByRole('button', { name: '继续这个项目' }));
    expect(onOpenProject).toHaveBeenCalledWith('novel-1');
    expect(within(region).getByText(/不会新建或复制任何内容/)).toBeTruthy();
  });

  it('can skip the creative intent without writing anything', async () => {
    const saveIntent = vi.fn(async () => savedIntent());
    render(<Host client={fakeClient({ saveIntent })} onOpenProject={vi.fn()} />);
    const region = panel();
    const intentRegion = within(region).getByRole('region', { name: '按创作意图开始' });
    fireEvent.click(within(intentRegion).getByRole('button', { name: '跳过创作意图，之后再说' }));
    expect(saveIntent).not.toHaveBeenCalled();
    expect(within(region).getByText(/已跳过创作意图设置/)).toBeTruthy();
  });

  it('creates a blank project only after a name is given', async () => {
    const createBlankProject = vi.fn(async () => ({ id: 'novel-new', title: '新项目', studio_ready: true, requires_scope_selection: false }));
    render(<Host client={fakeClient({ createBlankProject })} onOpenProject={vi.fn()} />);
    const region = panel();
    const blank = within(region).getByRole('region', { name: '空白开始' });
    const start = within(blank).getByRole('button', { name: '空白开始' }) as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    fireEvent.change(within(blank).getByLabelText('项目名称'), { target: { value: '新项目' } });
    await waitFor(() => expect((within(blank).getByRole('button', { name: '空白开始' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(within(blank).getByRole('button', { name: '空白开始' }));
    await waitFor(() => expect(createBlankProject).toHaveBeenCalledWith({ title: '新项目' }));
  });

  it('keeps the interface mode controlled and writes no browser storage', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const { container } = render(<Host client={fakeClient()} onOpenProject={vi.fn()} />);
    const modeRegion = within(panel()).getByRole('region', { name: '界面模式' });
    const novice = within(modeRegion).getByRole('radio', { name: '新手模式' });
    const professional = within(modeRegion).getByRole('radio', { name: '专业模式' });
    expect(novice.getAttribute('aria-checked')).toBe('true');
    expect(professional.getAttribute('aria-checked')).toBe('false');
    expect(within(modeRegion).getByText(/共用同一份项目、素材、任务与图谱数据/)).toBeTruthy();
    fireEvent.click(professional);
    await waitFor(() => expect(within(modeRegion).getByRole('radio', { name: '专业模式' }).getAttribute('aria-checked')).toBe('true'));
    expect(within(modeRegion).getByRole('radio', { name: '新手模式' }).getAttribute('aria-checked')).toBe('false');
    expect(setItem).not.toHaveBeenCalled();
    expect(container.querySelectorAll('[role="radio"]').length).toBe(2);
  });

  it('states a failed read as a failure instead of "no projects"', async () => {
    const listProjects = vi.fn(async () => { throw new ApiError({ status: 503, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }); });
    render(<Host client={fakeClient({ listProjects })} onOpenProject={vi.fn()} />);
    const region = panel();
    await waitFor(() => expect(within(region).getByText('请求未完成。 · STUDIO_REQUEST_FAILED')).toBeTruthy());
    expect(within(region).getByRole('button', { name: '重新读取' })).toBeTruthy();
    expect(within(region).queryByText('还没有项目')).toBeNull();
  });

  it('reports a resume target that cannot be re-read as invalid', async () => {
    const readIntent = vi.fn(async () => { throw new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED', message: '记录不可用。' }); });
    render(<Host client={fakeClient({ readIntent })} onOpenProject={vi.fn()} config={{ projectId: 'deleted-project' }} />);
    const region = panel();
    const alerts = () => within(region).getAllByRole('alert').map(node => node.textContent ?? '').join(' | ');
    await waitFor(() => expect(alerts()).toContain('已不可用'));
    expect(alerts()).toContain('不会自动创建一个替代项目');
    expect(within(region).queryByRole('button', { name: '继续这个项目' })).toBeNull();
  });

  it('re-opens by an explicitly typed project id', async () => {
    const readIntent = vi.fn(async () => savedIntent());
    render(<Host client={fakeClient({ readIntent })} onOpenProject={vi.fn()} />);
    const region = panel();
    fireEvent.change(within(region).getByLabelText('按编号重新打开'), { target: { value: 'novel-2' } });
    fireEvent.click(within(region).getByRole('button', { name: '重新打开' }));
    await waitFor(() => expect(readIntent).toHaveBeenCalledWith('novel-2', expect.anything()));
  });
});
