// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import type { ExperimentalFlags } from './api';
const captured = vi.hoisted(() => ({ import: vi.fn(), team: vi.fn(), inbox: vi.fn(), graph: vi.fn(), planning: vi.fn(), simulator: vi.fn() }));
vi.mock('./PlanningPanel', () => ({ PlanningPanel: (props: unknown) => { captured.planning(props); return <div>planning target</div>; } }));
vi.mock('./StorySimulatorPanel', () => ({ StorySimulatorPanel: (props: unknown) => { captured.simulator(props); return <div>simulator target</div>; } }));
vi.mock('./ImportPanel', () => ({ ImportPanel: (props: unknown) => { captured.import(props); return <div>import target</div>; } }));
vi.mock('./TeamsPanel', () => ({ TeamsPanel: (props: unknown) => { captured.team(props); return <div>team target</div>; } }));
vi.mock('./InboxPanel', () => ({ InboxPanel: (props: unknown) => { captured.inbox(props); return <div>inbox target</div>; } }));
vi.mock('./StoryGraphPanel', () => ({ StoryGraphPanel: (props: { onUseCharacter?: (character: string, chapter: string, scene?: string) => void }) => { captured.graph(props); return <button onClick={() => props.onUseCharacter?.('character-1', 'novel:1', 'scene-2')}>use scoped scene</button>; } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const flags = (key: string): ExperimentalFlags => ({ experimental: true, default_enabled: false, features: { [`experimental.${key}`]: true } });

it.each([
  ['advanced_planning_v2', 'planning_proposal', 'planning', 'requestedProposalId'],
  ['story_simulator_v2', 'simulator_run', 'simulator', 'requestedRunId'],
] as const)('forwards %s durable references only to their original owner', (feature, authority, name, key) => {
  const props = { novelId: 'novel', context: { sessionToken: '' }, flags: flags(feature) };
  const view = render(<ExperimentalWorkbench {...props} requestedTask={{ id: 'exact-original', authority }} />);
  expect(captured[name]).toHaveBeenLastCalledWith(expect.objectContaining({ [key]: 'exact-original' }));
  view.rerender(<ExperimentalWorkbench {...props} requestedTask={{ id: 'same-id', authority: 'other-owner' }} />);
  expect(captured[name]).toHaveBeenLastCalledWith(expect.objectContaining({ [key]: undefined }));
});

it('does not offer simulator navigation when its feature is disabled', () => {
  const navigate = vi.fn(), settings = flags('advanced_planning_v2');
  const props = { novelId: 'novel', context: { sessionToken: '' }, onNavigate: navigate };
  const view = render(<ExperimentalWorkbench {...props} flags={settings} />);
  expect(captured.planning).toHaveBeenLastCalledWith(expect.objectContaining({ onNavigate: undefined }));
  view.rerender(<ExperimentalWorkbench {...props} flags={{ ...settings, features: { ...settings.features, 'experimental.story_simulator_v2': true } }} />);
  expect(captured.planning).toHaveBeenLastCalledWith(expect.objectContaining({ onNavigate: navigate }));
});

it('enriches only simulator-origin planning callbacks at the real workbench host', () => {
  const navigate = vi.fn();
  render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('story_simulator_v2')} onNavigate={navigate} />);
  const child = captured.simulator.mock.calls.at(-1)![0] as { onNavigate: (target: unknown) => void };
  child.onNavigate({ kind: 'feature', id: 'proposal-one', feature: 'advanced_planning_v2' });
  expect(navigate).toHaveBeenLastCalledWith({ kind: 'feature', id: 'proposal-one', feature: 'advanced_planning_v2', task_authority: 'planning_proposal' });
  const chapter = { kind: 'chapter', id: 'chapter-one', version: 4 };
  child.onNavigate(chapter);
  expect(navigate).toHaveBeenLastCalledWith(chapter);
  child.onNavigate({ kind: 'feature', id: 'proposal-one', feature: 'advanced_planning_v2', task_authority: 'foreign' });
  expect(navigate).toHaveBeenCalledTimes(2);
});
