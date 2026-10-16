// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import type { ExperimentalFlags } from './api';
const captured = vi.hoisted(() => ({ import: vi.fn(), team: vi.fn(), inbox: vi.fn(), graph: vi.fn() }));
vi.mock('./ImportPanel', () => ({ ImportPanel: (props: unknown) => { captured.import(props); return <div>import target</div>; } }));
vi.mock('./TeamsPanel', () => ({ TeamsPanel: (props: unknown) => { captured.team(props); return <div>team target</div>; } }));
vi.mock('./InboxPanel', () => ({ InboxPanel: (props: unknown) => { captured.inbox(props); return <div>inbox target</div>; } }));
vi.mock('./StoryGraphPanel', () => ({ StoryGraphPanel: (props: { onUseCharacter?: (character: string, chapter: string, scene?: string) => void }) => { captured.graph(props); return <button onClick={() => props.onUseCharacter?.('character-1', 'novel:1', 'scene-2')}>use scoped scene</button>; } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const flags = (key: string): ExperimentalFlags => ({ experimental: true, default_enabled: false, features: { [`experimental.${key}`]: true } });
it.each([
  ['semantic_import_v2', 'semantic_import', 'import'],
  ['agent_team_recipes', 'agent_team', 'team'],
] as const)('forwards %s targets only to the matching original owner', (feature, authority, name) => {
  const props = { novelId: 'novel', context: { sessionToken: '' }, flags: flags(feature) };
  const view = render(<ExperimentalWorkbench {...props} requestedTask={{ id: 'owner-job', authority }} />);
  expect(captured[name]).toHaveBeenLastCalledWith(expect.objectContaining({ requestedTaskId: 'owner-job' }));
  view.rerender(<ExperimentalWorkbench {...props} requestedTask={{ id: 'foreign-job', authority: 'other-owner' }} />);
  expect(captured[name]).toHaveBeenLastCalledWith(expect.objectContaining({ requestedTaskId: undefined }));
});
it('preserves Review Inbox domain and rejects another owner target', () => {
  const props = { novelId: 'novel', context: { sessionToken: '' }, flags: flags('unified_review_inbox') };
  const view = render(<ExperimentalWorkbench {...props} requestedTask={{ id: 'review-1', authority: 'review_inbox', parent_id: 'narrative_judge' }} />);
  expect(captured.inbox).toHaveBeenLastCalledWith(expect.objectContaining({ requestedItemId: 'review-1', requestedDomain: 'narrative_judge' }));
  view.rerender(<ExperimentalWorkbench {...props} requestedTask={{ id: 'same-id', authority: 'media', parent_id: 'narrative_judge' }} />);
  expect(captured.inbox).toHaveBeenLastCalledWith(expect.objectContaining({ requestedItemId: undefined, requestedDomain: undefined }));
});
it('forwards the exact reviewed scene without dropping the chapter anchor', () => {
  const useCharacter = vi.fn();
  render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('temporal_story_graph_v2')} onUseCharacter={useCharacter} />);
  fireEvent.click(screen.getByRole('button', { name: 'use scoped scene' }));
  expect(useCharacter).toHaveBeenCalledTimes(1);
  expect(useCharacter).toHaveBeenCalledWith('character-1', 'novel:1', 'scene-2');
});
it('default OFF does not render or dispatch a requested owner target', () => {
  render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} requestedTask={{ id: 'job', authority: 'semantic_import' }} />);
  expect(captured.import).not.toHaveBeenCalled();
  expect(screen.getByText('Experimental 未启用')).toBeTruthy();
});
