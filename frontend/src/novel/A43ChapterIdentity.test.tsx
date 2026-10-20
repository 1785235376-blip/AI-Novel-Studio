// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { AgentTeamPanel } from './AgentTeamPanel';
import { AiContextPreviewPanel } from './AiContextPreviewPanel';

const chapterId = 'legacy:~11111111-1111-4111-8111-111111111111';
const replacementId = 'legacy:~22222222-2222-4222-8222-222222222222';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function wrapper(children: React.ReactNode, client = new QueryClient({defaultOptions: {queries: {retry: false}}})) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('A43 stable chapter consumers', () => {
  it('submits the selected typed identity to the agent job owner', async () => {
    vi.spyOn(api, 'agents').mockResolvedValue({catalog_version: '1.0', agents: [{id: 'planner', name: '策划 Agent', description: '负责大纲。', prompt_role: 'plot_planner', tools: ['outline.read'], output_schema: 'story_plan_proposal', requires_approval: true}]});
    vi.spyOn(api, 'textModels').mockResolvedValue([]);
    const create = vi.spyOn(api, 'createAgentJob').mockResolvedValue({id: 'typed-job', status: 'QUEUED'});
    vi.spyOn(api, 'startAgentJob').mockResolvedValue({id: 'typed-job', status: 'VALIDATED', execution_mode: 'deterministic', result: {structured_output: {summary: 'Synthetic', proposals: [], findings: []}}});
    render(wrapper(<AgentTeamPanel chapter={{id: chapterId, novel_id: 'legacy', number: 1, title: 'Typed owner'} as any}/>));
    await screen.findByLabelText('任务说明');
    fireEvent.click(screen.getByRole('button', {name: '启动任务'}));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({novel_id: 'legacy', chapter: 1, chapter_id: chapterId})));
  });

  it('binds context preview refresh to full identity despite an equal display number', async () => {
    const context = vi.spyOn(api, 'agentContext').mockImplementation(async (_agent, _novel, _number, _instruction, _target, id) => ({chapter_id: id, sections: {}}));
    vi.spyOn(api, 'writingGoal').mockResolvedValue({} as any);
    vi.spyOn(api, 'resource').mockResolvedValue([]);
    vi.spyOn(api, 'worldRules').mockResolvedValue({items: [], storage: 'file'});
    const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
    const panel = (id: string) => wrapper(<AiContextPreviewPanel novelId='legacy' chapterNumber={1} chapterVersion={1} chapterId={id} operation='continue' instruction='' />, client);
    const view = render(panel(chapterId));
    fireEvent.click(screen.getByRole('button', {name: '刷新上下文'}));
    await waitFor(() => expect(context).toHaveBeenCalledWith('writer', 'legacy', 1, '', 'local', chapterId));
    const priorCalls = context.mock.calls.length;
    view.rerender(panel(replacementId));
    await waitFor(() => expect(screen.queryByText('资料已读取')).toBeNull());
    expect(context.mock.calls).toHaveLength(priorCalls);
    fireEvent.click(screen.getByRole('button', {name: '刷新上下文'}));
    await waitFor(() => expect(context).toHaveBeenLastCalledWith('writer', 'legacy', 1, '', 'local', replacementId));
  });
});
