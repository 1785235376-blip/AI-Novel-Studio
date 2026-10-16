// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { IntentPicker } from './IntentPicker';
import { studioIntentState } from './studioEntryContract';
import { STUDIO_INTENT_IDS, STUDIO_INTENT_LABELS, type StudioEntryClient, type StudioEntryIntent, type StudioIntentDraft } from './studioEntryTypes';
import { useStudioEntry } from './useStudioEntry';

const rows = [{ id: 'novel-1', title: '第一个项目', updated_at: null, entry_kind: 'NEUTRAL_STUDIO', genre: null, status: null }];
const savedIntent = (version: number, selected: string[] = [], customLabel = '我的短片'): StudioEntryIntent => studioIntentState({
  version, preset: 'TEXT', editable: true, history_retained: true,
  values: STUDIO_INTENT_IDS.map(intent_id => ({
    intent_id, selected: selected.includes(intent_id), custom: intent_id === 'custom',
    label: intent_id === 'custom' ? (customLabel || '自定义') : STUDIO_INTENT_LABELS[intent_id],
  })),
}, 'novel-1');
function fakeClient(patch: Partial<Record<keyof StudioEntryClient, unknown>> = {}) {
  const client = {
    listProjects: vi.fn(async () => rows),
    createBlankProject: vi.fn(),
    readIntent: vi.fn(async () => savedIntent(1)),
    saveIntent: vi.fn(async () => savedIntent(2, ['image_design'])),
    ...patch,
  };
  return client as unknown as StudioEntryClient;
}
function Host({ client }: { client: StudioEntryClient }) {
  const controller = useStudioEntry({ client, identity: 'entry-session', active: true, projectId: 'novel-1' });
  return <IntentPicker controller={controller} />;
}
/** The region node is re-read on every step: the picker re-renders as the controller settles. */
const picker = () => screen.getByRole('region', { name: '创作意图设置' });
const inPicker = () => within(picker());

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('creative intent picker', () => {
  it('multi-selects and states that intent only affects recommendations', async () => {
    render(<Host client={fakeClient()} />);
    await waitFor(() => expect(inPicker().getByText('已保存 v1')).toBeTruthy());
    expect(inPicker().getByText(/只影响推荐布局与提示，不是权限/)).toBeTruthy();
    expect(inPicker().getByText(/不会限制可用模块/)).toBeTruthy();
    expect(inPicker().getByText(/不会触发任何生成/)).toBeTruthy();
    const writing = inPicker().getByLabelText('小说创作') as HTMLInputElement;
    const image = inPicker().getByLabelText('图片设计') as HTMLInputElement;
    expect(writing.checked).toBe(false);
    fireEvent.click(writing);
    fireEvent.click(image);
    expect((inPicker().getByLabelText('小说创作') as HTMLInputElement).checked).toBe(true);
    expect((inPicker().getByLabelText('图片设计') as HTMLInputElement).checked).toBe(true);
    // A multi-select stays editable and reports the unsaved local choice.
    fireEvent.click(inPicker().getByLabelText('图片设计'));
    expect((inPicker().getByLabelText('图片设计') as HTMLInputElement).checked).toBe(false);
    expect(inPicker().getByText('未保存的本地选择')).toBeTruthy();
  });

  it('edits the custom label and refuses to save a selected custom intent without a name', async () => {
    const saveIntent = vi.fn(async () => savedIntent(2, ['custom'], '我的新片'));
    render(<Host client={fakeClient({ saveIntent })} />);
    await waitFor(() => expect(inPicker().getByText('已保存 v1')).toBeTruthy());
    // The custom entry's checkbox carries the author's own saved text, never a second field.
    fireEvent.click(inPicker().getByRole('checkbox', { name: '我的短片' }));
    fireEvent.change(inPicker().getByLabelText('自定义创作意图名称'), { target: { value: '   ' } });
    expect(inPicker().getByText(/自定义创作意图需要 1–120 个字符的名称。/)).toBeTruthy();
    const save = inPicker().getByRole('button', { name: '保存创作意图' }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(save);
    expect(saveIntent).not.toHaveBeenCalled();

    fireEvent.change(inPicker().getByLabelText('自定义创作意图名称'), { target: { value: '我的新片' } });
    await waitFor(() => expect((inPicker().getByRole('button', { name: '保存创作意图' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(inPicker().getByRole('button', { name: '保存创作意图' }));
    await waitFor(() => expect(saveIntent).toHaveBeenCalledTimes(1));
    const draft = (saveIntent.mock.calls as unknown[][])[0][1] as StudioIntentDraft;
    expect(draft.values.find(item => item.intent_id === 'custom')?.label).toBe('我的新片');
    expect(await inPicker().findByText(/创作意图已保存 · v2。/)).toBeTruthy();
  });

  it('keeps the local selection when the owner answers with a version conflict', async () => {
    const readIntent = vi.fn()
      .mockResolvedValueOnce(savedIntent(3))
      .mockResolvedValueOnce(savedIntent(5));
    // The client seam maps a 409 to this bounded text; the picker must keep the draft.
    const saveIntent = vi.fn()
      .mockRejectedValueOnce(new ApiError({ status: 409, code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', message: '创作意图已被其他会话更新。当前输入仍保留，请核对最新版本后重新提交。' }))
      .mockResolvedValue(savedIntent(6, ['image_design']));
    render(<Host client={fakeClient({ readIntent, saveIntent })} />);
    await waitFor(() => expect(inPicker().getByText('已保存 v3')).toBeTruthy());
    fireEvent.click(inPicker().getByLabelText('图片设计'));
    fireEvent.click(inPicker().getByRole('button', { name: '保存创作意图' }));
    // The conflict banner is a warning status message; a bounded problem alert may also be present.
    const text = () => [...inPicker().queryAllByRole('alert'), ...inPicker().queryAllByRole('status')].map(node => node.textContent ?? '').join(' | ');
    await waitFor(() => expect(text()).toContain('版本冲突'));
    // The conflict text is bounded, and the user's own draft is still on screen.
    expect(text()).toContain('你的选择仍保留');
    expect(text()).not.toContain('raw conflict');
    expect((inPicker().getByLabelText('图片设计') as HTMLInputElement).checked).toBe(true);
    expect(readIntent).toHaveBeenCalledTimes(2);
    fireEvent.click(inPicker().getByRole('button', { name: '已核对，保留我的选择' }));
    await waitFor(() => expect((inPicker().getByRole('button', { name: '保存创作意图' }) as HTMLButtonElement).disabled).toBe(false));
    expect(text()).not.toContain('版本冲突');
    expect(inPicker().getAllByText(/本地选择仍保留/).length).toBeGreaterThan(0);
    // After re-reading version 5 the draft is resubmitted against the served version.
    fireEvent.click(inPicker().getByRole('button', { name: '保存创作意图' }));
    await waitFor(() => expect(saveIntent).toHaveBeenCalledTimes(2));
    expect(saveIntent.mock.calls[1][1].expected_version).toBe(5);
    expect(await inPicker().findByText('已保存 v6')).toBeTruthy();
  });

  it('offers a first-class skip that writes no preference', async () => {
    const saveIntent = vi.fn();
    render(<Host client={fakeClient({ saveIntent })} />);
    await waitFor(() => expect(inPicker().getByText('已保存 v1')).toBeTruthy());
    fireEvent.click(inPicker().getByLabelText('小说创作'));
    fireEvent.click(inPicker().getByRole('button', { name: '跳过（稍后设置）' }));
    expect(saveIntent).not.toHaveBeenCalled();
    expect((inPicker().getByLabelText('小说创作') as HTMLInputElement).checked).toBe(false);
    expect(await inPicker().findByText(/已跳过创作意图设置/)).toBeTruthy();
  });
});
