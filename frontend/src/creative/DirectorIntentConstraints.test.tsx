// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import { DirectorTargetPanel } from './DirectorTargetPanel';
import { checkedVisualTarget } from './studioProductionGraphContract';
import { compareDirectorDraft } from './directorDraftComparison';
import { creativeAuthoringProblems, documentInput, newDocument, validDirectorIntent, type CreativeDocument, type CreativeInput } from './types';
const legacy = { style: '', atmosphere: '', reference_works: [], color: '', rhythm: '' };
const target = { ...legacy, target_audience: 'First-time viewers', target_platform: 'Local screening', production_budget_constraints: 'Use existing sets; no paid cloud calls' };
afterEach(cleanup);
describe('authored Director audience/platform/budget constraints', () => {
  it('preserves absent legacy fields, rejects invalid context, and compares only explicit intent', () => {
    expect(checkedVisualTarget(legacy)).toEqual(legacy);
    expect(Object.hasOwn(checkedVisualTarget(legacy), 'target_audience')).toBe(false);
    expect(checkedVisualTarget(target)).toEqual(target);
    for (const key of ['target_audience', 'target_platform', 'production_budget_constraints'] as const) {
      expect(() => checkedVisualTarget({ ...target, [key]: true })).toThrow();
      expect(() => checkedVisualTarget({ ...target, [key]: 'x'.repeat(2001) })).toThrow();
      expect(checkedVisualTarget({ ...target, [key]: '🎬'.repeat(2000) })[key]).toHaveLength(4000);
      expect(validDirectorIntent({ ...target, [key]: 'x'.repeat(2001) })).toBe(false);
      expect(creativeAuthoringProblems({ ...newDocument('DIRECTOR'), visual_target: { ...target, [key]: 'x'.repeat(2001) } })).toHaveLength(1);
    }
    expect(() => checkedVisualTarget({ ...target, execution_authority: true })).toThrow();
    const authored = { ...newDocument('DIRECTOR'), visual_target: target };
    expect(documentInput(authored).visual_target).toEqual(target);
    expect(compareDirectorDraft(authored, { ...authored, visual_target: legacy }).map(row => row.path)).toEqual([
      'visual/target_audience', 'visual/target_platform', 'visual/production_budget_constraints']);
  });
  it('clears an optional constraint without manufacturing an empty/default field', () => {
    const onChange = vi.fn(); render(<DirectorTargetPanel value={target} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('目标受众'), { target: { value: '   ' } });
    expect(onChange).toHaveBeenCalledWith({ ...legacy, target_platform: target.target_platform, production_budget_constraints: target.production_budget_constraints });
    expect(screen.getByText(/费用和可行性尚未核实/)).toBeTruthy();
  });
  it('edits, explicitly saves and reopens through the original graph Director console', async () => {
    let stored: CreativeDocument = { ...newDocument('DIRECTOR'), id: 'd1', source_independent: true, title: 'Saved director', version: 1, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
    const client: GraphDirectorSource = {
      history: vi.fn(), derive: vi.fn(),
      list: vi.fn(async () => ({ items: [stored] })),
      capabilities: vi.fn(async () => ({ enabled: true, can_mutate: true, modes: ['DIRECTOR' as const] })),
      create: vi.fn(async (input: CreativeInput) => stored = { ...stored, ...input }),
      update: vi.fn(async (id: string, version: number, input: CreativeInput) => stored = { ...stored, ...input, id, version: version + 1 }),
      export: vi.fn(async () => ({ document: structuredClone(stored), document_digest: 'a'.repeat(64), format: '', boundary: '' })),
    };
    const props = { client, active: true, canMutate: true, busy: false, isCurrent: () => true,
      read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange: vi.fn() };
    const open = async () => { fireEvent.click(screen.getByRole('button', { name: '打开导演总控台' })); await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false)); };
    const view = render(<GraphDirectorConsole {...props} />); await open();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Intent draft' } });
    for (const [label, value] of [['目标受众', target.target_audience], ['目标平台', target.target_platform], ['制作预算约束（作者设定）', target.production_budget_constraints]])
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    expect(client.create).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText(/导演原文档已保存/);
    expect(vi.mocked(client.create).mock.calls[0][0].visual_target).toEqual(target);
    view.unmount(); render(<GraphDirectorConsole {...props} pin={{ id: 'd1', version: 1, digest: 'a'.repeat(64) }} />); await open();
    fireEvent.click(screen.getByRole('button', { name: '读取选中导演节点原文档' }));
    await screen.findByDisplayValue(target.target_audience);
    expect(screen.getByDisplayValue(target.target_platform)).toBeTruthy();
    expect(screen.getByDisplayValue(target.production_budget_constraints)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('目标平台'), { target: { value: 'x'.repeat(2001) } });
    expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
    expect(client.update).not.toHaveBeenCalled(); expect(client.derive).not.toHaveBeenCalled();
    expect(stored.status).toBe('DRAFT');
  });
});
