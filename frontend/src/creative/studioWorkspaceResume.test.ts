// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { readLocalStudioResume, rememberLocalStudioResume } from './studioWorkspaceResume';

afterEach(() => localStorage.clear());
const record = { schema: 1, mode: 'local', actor: 'local-author', project_id: 'project-a',
  module: 'VIDEO', view: 'GRAPH', stage: 'M6', graph_id: 'graph-a', run_id: 'run-a' };
const stored = (value: unknown) => ({ getItem: () => JSON.stringify(value) });

it('retains navigation IDs while discarding all caller-provided private fields', () => {
  expect(rememberLocalStudioResume('project-a', {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
    ...{ prompt: 'private author input', sessionToken: 'private token' },
  })).toBe(true);
  expect(JSON.parse(localStorage.getItem(localStorage.key(0)!)!)).toEqual(record);
  expect(readLocalStudioResume('project-a')).toEqual({ state: 'SAVED', location: {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
  } });
});

it('never adopts an old project, actor, scope or malformed execution hint', () => {
  expect(readLocalStudioResume('other-project', stored(record))).toEqual({ state: 'EMPTY' });
  for (const value of [
    { ...record, actor: 'another-author' }, { ...record, mode: 'collaboration' },
    { ...record, session_token: 'must-not-be-restored' }, { ...record, dispatch: true },
    { ...record, graph_id: undefined }, { ...record, run_id: '\u0000private' },
    { ...record, stage: 'M12' }, { ...record, schema: 2 },
  ]) expect(readLocalStudioResume('project-a', stored(value))).toEqual({ state: 'INVALID' });
});

it('treats unavailable storage separately from an empty server workspace', () => {
  expect(readLocalStudioResume('project-a', { getItem: () => { throw new Error('blocked'); } }))
    .toEqual({ state: 'UNAVAILABLE' });
  expect(rememberLocalStudioResume('project-a', { module: 'VIDEO', view: 'PRODUCTION', stage: 'M9' },
    { setItem: () => { throw new Error('quota'); } })).toBe(false);
  expect(rememberLocalStudioResume('project-a', { module: 'VIDEO', view: 'GRAPH', stage: 'M4', runId: 'orphan' })).toBe(false);
});
