// @vitest-environment jsdom
import { useLayoutEffect, useRef } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api, type Chapter, type CreativeAgent, type CreativeAgentCatalog } from '../api';
import { clearLocalHostSession } from '../localHostSession';
import { useStudio } from '../store';
import { AgentTeamPanel } from './AgentTeamPanel';

const verifier: CreativeAgent = {
  id: 'verifier', name: '核验 Agent', description: '核验世界与人物。',
  prompt_role: 'verifier', tools: ['context.read', 'chapter.read'],
  output_schema: 'verification_findings', requires_approval: false,
};
const planner: CreativeAgent = {
  ...verifier, id: 'planner', name: '策划 Agent', description: '负责大纲。',
  requires_approval: true,
};
const reviewer: CreativeAgent = {
  ...verifier, id: 'reviewer', name: '审核 Agent', description: '审核已保存章节。',
};
const chapter: Chapter = {
  id: 'n:1', novel_id: 'n', number: 1, title: '第一章', content: '',
  document: null, version: 2, word_count: 0, status: 'DRAFT',
};
const clients: QueryClient[] = [];
const catalog = (agents: CreativeAgent[]): CreativeAgentCatalog => ({
  catalog_version: 'selection-boundary', agents: [], additional_agents: agents,
});
type Selection = { id: string; description: string };

// A real parent layout effect observes the usable DOM before the child's passive
// selection repair. Neither React effects nor TanStack hooks are mocked.
function CommitProbe({ onCommit }: { onCommit?: (selection: Selection, start: HTMLButtonElement) => void }) {
  const root = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const select = root.current?.querySelector<HTMLSelectElement>('select');
    const form = select?.closest('section');
    const start = Array.from(form?.querySelectorAll('button') ?? [])
      .find(button => button.textContent === '启动任务');
    if (select && start && !start.disabled) {
      onCommit?.({
        id: select.value,
        description: form?.querySelector('p.novel-help')?.textContent ?? '',
      }, start);
    }
  });
  return <div ref={root}><AgentTeamPanel chapter={chapter} /></div>;
}

function mount(agents: CreativeAgent[], onCommit?: Parameters<typeof CommitProbe>[0]['onCommit'],
  onMutate?: (variables: unknown) => void | Promise<void>) {
  const client = new QueryClient({
    mutationCache: new MutationCache({ onMutate }),
    defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } },
  });
  clients.push(client);
  client.setQueryData(['creative-agent-catalog'], catalog(agents));
  client.setQueryData(['text-models'], []);
  const tree = (probe?: typeof onCommit) =>
    <QueryClientProvider client={client}><CommitProbe onCommit={probe} /></QueryClientProvider>;
  const view = render(tree(onCommit));
  return {
    replace(next: CreativeAgent[], probe?: typeof onCommit) {
      act(() => {
        client.setQueryData(['creative-agent-catalog'], catalog(next));
        view.rerender(tree(probe));
      });
    },
  };
}

beforeEach(() => {
  useStudio.getState().setCollaboration('');
  useStudio.getState().setTextModel(null);
  clearLocalHostSession();
  vi.spyOn(api, 'agents').mockResolvedValue(catalog([]));
  vi.spyOn(api, 'textModels').mockResolvedValue([]);
  vi.spyOn(api, 'createAgentJob').mockResolvedValue({ id: 'selection-job', status: 'QUEUED' });
  vi.spyOn(api, 'startAgentJob').mockResolvedValue({
    id: 'selection-job', status: 'VALIDATED', execution_mode: 'deterministic',
  });
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach(client => client.clear());
  clearLocalHostSession();
  vi.restoreAllMocks();
});

it('shows the registered default and its description together at the first usable commit', async () => {
  const commits: Selection[] = [];
  mount([verifier], (selection, start) => {
    commits.push(selection);
    start.click();
  });
  expect.soft(commits).toEqual([{ id: verifier.id, description: verifier.description }]);
  await waitFor(() => expect(api.createAgentJob).toHaveBeenCalledTimes(1));
  expect(api.createAgentJob).toHaveBeenCalledWith(expect.objectContaining({
    agent_id: verifier.id, novel_id: chapter.novel_id, chapter: chapter.number,
    chapter_id: chapter.id, execution_mode: 'deterministic', target: 'local',
  }));
  expect(api.startAgentJob).toHaveBeenCalledTimes(1);
  expect(api.startAgentJob).toHaveBeenCalledWith('selection-job');
});

it('captures the displayed role as mutation input even if the catalog changes before execution', async () => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const onMutate = vi.fn((_variables: unknown) => gate);
  const view = mount([verifier], undefined, onMutate);
  fireEvent.click(screen.getByRole('button', { name: '启动任务' }));
  await waitFor(() => expect(onMutate).toHaveBeenCalledTimes(1));
  view.replace([reviewer]);
  expect((screen.getByLabelText('Agent 角色') as HTMLSelectElement).value).toBe(reviewer.id);
  // Global MutationCache receives variables plus the mutation and context.
  expect.soft(vi.mocked(onMutate).mock.calls[0]?.[0]).toBe(verifier.id);
  release();
  await waitFor(() => expect(api.createAgentJob).toHaveBeenCalledTimes(1));
  expect(api.createAgentJob).toHaveBeenCalledWith(expect.objectContaining({ agent_id: verifier.id }));
  expect(api.startAgentJob).toHaveBeenCalledTimes(1);
  expect(api.startAgentJob).toHaveBeenCalledWith('selection-job');
});

it('uses the new registered fallback at the first commit after the selected role is removed', async () => {
  const view = mount([planner, reviewer]);
  const commits: Selection[] = [];
  view.replace([verifier], (selection, start) => {
    commits.push(selection);
    start.click();
  });
  expect.soft(commits).toEqual([{ id: verifier.id, description: verifier.description }]);
  await waitFor(() => expect(api.createAgentJob).toHaveBeenCalledTimes(1));
  expect(api.createAgentJob).toHaveBeenCalledWith(expect.objectContaining({ agent_id: verifier.id }));
  expect(api.startAgentJob).toHaveBeenCalledTimes(1);
  expect(api.startAgentJob).toHaveBeenCalledWith('selection-job');
});

it('preserves the author\'s explicit registered choice when the catalog is reordered', async () => {
  const view = mount([planner, verifier]);
  fireEvent.change(screen.getByLabelText('Agent 角色'), { target: { value: verifier.id } });
  const commits: Selection[] = [];
  view.replace([reviewer, planner, verifier], (selection, start) => {
    commits.push(selection);
    start.click();
  });
  expect(commits).toEqual([{ id: verifier.id, description: verifier.description }]);
  await waitFor(() => expect(api.createAgentJob).toHaveBeenCalledTimes(1));
  expect(api.createAgentJob).toHaveBeenCalledWith(expect.objectContaining({ agent_id: verifier.id }));
});

it('retains a registered planner default even when another role is listed first', async () => {
  const commits: Selection[] = [];
  mount([reviewer, planner], (selection, start) => {
    commits.push(selection);
    start.click();
  });
  expect(commits).toEqual([{ id: planner.id, description: planner.description }]);
  await waitFor(() => expect(api.createAgentJob).toHaveBeenCalledTimes(1));
  expect(api.createAgentJob).toHaveBeenCalledWith(expect.objectContaining({ agent_id: planner.id }));
});

it.each(['initially empty', 'replaced with empty'])('does not offer or create a job when the catalog is %s', kind => {
  const view = mount(kind === 'initially empty' ? [] : [planner]);
  if (kind === 'replaced with empty') view.replace([]);
  expect(screen.getByText('暂无 Agent')).toBeTruthy();
  expect(screen.queryByLabelText('Agent 角色')).toBeNull();
  expect(screen.queryByRole('button', { name: '启动任务' })).toBeNull();
  expect(api.createAgentJob).not.toHaveBeenCalled();
  expect(api.startAgentJob).not.toHaveBeenCalled();
});
