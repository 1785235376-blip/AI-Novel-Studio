// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StoryFactUsagePanel } from './StoryFactUsagePanel';
import { checkedFacts, checkedImpact, type FactTarget } from './storyFactClient';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
afterEach(cleanup);
const fact = { id: 'fact-1', version: 1, digest: 'a'.repeat(64), title: '已批准的事实' };
const target: FactTarget = { document_id: 'doc', document_version: 2, document_digest: 'b'.repeat(64), scene_id: 'scene', shot_id: 'shot', shot_version: 1, shot_digest: 'c'.repeat(64) };
const row = { id: 'use-1', version: 1, fact, current_fact: { ...fact, status: 'APPROVED' }, target, state: 'CURRENT', blockers: [], purpose: 'CAUSAL_CONTEXT', rationale: '解释动作', assets: [{ asset_id: 'image-1', version: 3, digest: 'd'.repeat(64), kind: 'image' }] };
const sources = { contract: 'creative-story-facts/1', coverage: 'APPROVED_WORLD_FACT_RELATIONS_ONLY', items: [fact] };
const impact = (items: unknown[] = []) => ({ contract: 'creative-fact-impact/1', coverage: 'EXPLICIT_CONFIRMED_FACT_USES_AND_CURRENT_SHOT_ASSET_BINDINGS', unrecorded_dependencies: 'UNKNOWN', automatic_regeneration: false, model_called: false, items });
function setup() {
  let saved = false;
  const json = vi.fn(async (url: string, method?: string): Promise<unknown> => {
    if (method === 'POST') { saved = true; return { id: 'use-1', version: 1, status: 'CONFIRMED' }; }
    return url.endsWith('/story-facts') ? sources : impact(saved ? [row] : []);
  });
  const gate = async <T,>(work: () => Promise<T>): Promise<T> => work();
  const readMock = vi.fn(gate), mutateMock = vi.fn(gate);
  const read = readMock as typeof gate & typeof readMock;
  const mutate = mutateMock as typeof gate & typeof mutateMock;
  return { projectId: 'p', identity: 'scope-1', target, enabled: true, writable: true, busy: false,
    isCurrent: () => true, transport: { json } as StudioGraphTransport, read, mutate, json };
}
async function inspect() { fireEvent.click(screen.getByRole('button', { name: '读取事实依赖' })); await screen.findByRole('option', { name: /已批准的事实/ }); }
describe('story fact usage', () => {
  it('discloses original-project eligibility, legacy handling and unevaluated coverage', () => {
    const props = setup(); render(<StoryFactUsagePanel {...props} />);
    expect(screen.getByText(/当前原项目世代中新建并明确批准/)).toBeTruthy();
    expect(screen.getByText(/旧版或未绑定的记录仍可在原 Story Graph 阅读/)).toBeTruthy();
    expect(screen.getByText(/复制或新建候选并审核批准，不会静默迁移/)).toBeTruthy();
    expect(screen.getByText(/未评估时间推理、语义因果或 Export 影响；成本未知/)).toBeTruthy();
    expect(props.json).not.toHaveBeenCalled();
  });
  it('does not read automatically or when host is unavailable', () => {
    const props = setup(); const { rerender } = render(<StoryFactUsagePanel {...props} />); expect(props.json).not.toHaveBeenCalled();
    rerender(<StoryFactUsagePanel {...props} enabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: '读取事实依赖' })); expect(props.json).not.toHaveBeenCalled();
  });
  it('requires explicit source, reason and confirmation, then read-verifies exact pins', async () => {
    const props = setup(); render(<StoryFactUsagePanel {...props} />); await inspect();
    const submit = screen.getByRole('button', { name: '确认事实使用' }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('已批准事实'), { target: { value: fact.id } });
    fireEvent.change(screen.getByLabelText('使用理由'), { target: { value: row.rationale } });
    expect(submit.disabled).toBe(true); fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(submit); await screen.findByText(/已回读确认事实使用记录/);
    expect(props.mutate).toHaveBeenCalledTimes(1);
    expect(props.json).toHaveBeenCalledWith('/api/novels/p/experimental/creative/documents/doc/shots/shot/fact-uses', 'POST', {
      expected_version: 2, document_digest: target.document_digest, shot_version: 1, shot_digest: target.shot_digest,
      fact: { id: fact.id, version: fact.version, digest: fact.digest }, purpose: 'CAUSAL_CONTEXT', rationale: row.rationale, confirmed: true,
    });
    expect(screen.getByText(/image 素材 image-1 v3/)).toBeTruthy();
  });
  it('shows stale blockers and bounded impact without offering regeneration', async () => {
    const props = setup(); props.json.mockImplementation(async url => url.endsWith('/story-facts') ? sources : impact([{ ...row, state: 'STALE', blockers: ['FACT_VERSION_CHANGED'] }]));
    render(<StoryFactUsagePanel {...props} writable={false} />); await inspect();
    expect(screen.getByText(/FACT_VERSION_CHANGED/)).toBeTruthy();
    expect(screen.getByText(/未记录的依赖未知/)).toBeTruthy();
    expect((screen.getByRole('button', { name: '确认事实使用' }) as HTMLButtonElement).disabled).toBe(true);
    expect(props.mutate).not.toHaveBeenCalled();
  });
  it('discards delayed responses after context changes and does not reopen on A-B-A', async () => {
    const props = setup(); let resolve!: (v: unknown) => void;
    props.json.mockImplementationOnce(() => new Promise(r => { resolve = r; }) as ReturnType<typeof props.json>);
    const { rerender } = render(<StoryFactUsagePanel {...props} />);
    fireEvent.click(screen.getByRole('button', { name: '读取事实依赖' }));
    rerender(<StoryFactUsagePanel {...props} identity="scope-2" />);
    resolve(impact([row])); await waitFor(() => expect(screen.queryByText(/固定事实 fact-1/)).toBeNull());
    rerender(<StoryFactUsagePanel {...props} />); expect(props.json).toHaveBeenCalledTimes(1);
  });
  it('clears source confirmation when selection or rationale changes', async () => {
    const props = setup(); render(<StoryFactUsagePanel {...props} />); await inspect();
    fireEvent.change(screen.getByLabelText('已批准事实'), { target: { value: fact.id } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.change(screen.getByLabelText('使用理由'), { target: { value: 'changed' } });
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
  });
  it('drops loaded facts and consent when target pins change', async () => {
    const props = setup(); const { rerender } = render(<StoryFactUsagePanel {...props} />); await inspect();
    fireEvent.change(screen.getByLabelText('已批准事实'), { target: { value: fact.id } });
    fireEvent.click(screen.getByRole('checkbox'));
    rerender(<StoryFactUsagePanel {...props} target={{ ...target, shot_version: 2, shot_digest: 'e'.repeat(64) }} />);
    expect(screen.queryByRole('checkbox')).toBeNull(); expect(props.json).toHaveBeenCalledTimes(2);
  });
  it('reports rejected writes without automatic retry or successful readback claim', async () => {
    const props = setup(); render(<StoryFactUsagePanel {...props} />); await inspect();
    props.mutate.mockRejectedValueOnce(new Error('AUTHORITY_REQUIRED'));
    fireEvent.change(screen.getByLabelText('已批准事实'), { target: { value: fact.id } });
    fireEvent.change(screen.getByLabelText('使用理由'), { target: { value: row.rationale } });
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: '确认事实使用' }));
    await screen.findByText('AUTHORITY_REQUIRED'); expect(props.mutate).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/已回读确认事实使用记录/)).toBeNull();
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
  });
  it('fails closed on malformed or overclaiming responses', () => {
    expect(() => checkedFacts({ ...sources, coverage: 'ALL' })).toThrow();
    expect(() => checkedImpact({ ...impact(), automatic_regeneration: true }, 'doc')).toThrow();
    expect(() => checkedImpact(impact([{ ...row, target: { ...target, document_id: 'foreign' } }]), 'doc')).toThrow();
    expect(() => checkedImpact(impact([{ ...row, fact: { ...fact, digest: 'missing' } }]), 'doc')).toThrow();
  });
});
