// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import {
  DEFAULT_STUDIO_INTERFACE_MODE, readLocalStudioInterfaceMode,
  readLocalStudioResume, rememberLocalStudioInterfaceMode, rememberLocalStudioResume,
} from './studioWorkspaceResume';

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

it('round-trips the presentation mode without converting any other saved field', () => {
  expect(rememberLocalStudioResume('project-a', {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
    interfaceMode: 'PROFESSIONAL',
  })).toBe(true);
  expect(readLocalStudioResume('project-a')).toEqual({ state: 'SAVED', location: {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
    interfaceMode: 'PROFESSIONAL',
  } });
  expect(readLocalStudioInterfaceMode('project-a')).toBe('PROFESSIONAL');
});

it('defaults to today\'s full interface and only honours an explicitly saved mode', () => {
  // Adding a presentation mode must never change an existing interface: an
  // absent, older or unreadable record keeps the full workspace.
  expect(DEFAULT_STUDIO_INTERFACE_MODE).toBe('PROFESSIONAL');
  expect(readLocalStudioInterfaceMode('project-a')).toBe('PROFESSIONAL');
  expect(readLocalStudioInterfaceMode('project-a', stored(record))).toBe('PROFESSIONAL');
  expect(readLocalStudioInterfaceMode('other-project', stored(record))).toBe('PROFESSIONAL');
  expect(readLocalStudioInterfaceMode('project-a', { getItem: () => { throw new Error('blocked'); } })).toBe('PROFESSIONAL');
  expect(readLocalStudioInterfaceMode('project-a', stored({ ...record, interface_mode: 'EXPERT' }))).toBe('PROFESSIONAL');
  // An explicit novice choice is restored.
  expect(readLocalStudioInterfaceMode('project-a', stored({ ...record, interface_mode: 'NOVICE' }))).toBe('NOVICE');
});

it('rejects a malformed presentation mode instead of adopting it', () => {
  for (const value of [{ ...record, interface_mode: 'EXPERT' }, { ...record, interface_mode: '' },
    { ...record, interface_mode: 1 }]) {
    expect(readLocalStudioResume('project-a', stored(value))).toEqual({ state: 'INVALID' });
  }
  expect(rememberLocalStudioResume('project-a', {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6',
    interfaceMode: 'EXPERT' as never,
  })).toBe(false);
});

it('switching mode merges into the saved location and preserves every other field', () => {
  expect(rememberLocalStudioResume('project-a', {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
  })).toBe(true);
  expect(rememberLocalStudioInterfaceMode('project-a', 'PROFESSIONAL')).toBe(true);
  expect(readLocalStudioResume('project-a')).toEqual({ state: 'SAVED', location: {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
    interfaceMode: 'PROFESSIONAL',
  } });
  expect(rememberLocalStudioInterfaceMode('project-a', 'NOVICE')).toBe(true);
  expect(readLocalStudioInterfaceMode('project-a')).toBe('NOVICE');
  expect(readLocalStudioResume('project-a')).toEqual({ state: 'SAVED', location: {
    module: 'VIDEO', view: 'GRAPH', stage: 'M6', graphId: 'graph-a', runId: 'run-a',
    interfaceMode: 'NOVICE',
  } });
});

it('refuses to fabricate a saved location just to store a mode', () => {
  expect(rememberLocalStudioInterfaceMode('project-a', 'PROFESSIONAL')).toBe(false);
  expect(readLocalStudioResume('project-a')).toEqual({ state: 'EMPTY' });
  expect(rememberLocalStudioInterfaceMode('project-a', 'EXPERT' as never)).toBe(false);
  expect(rememberLocalStudioInterfaceMode('', 'PROFESSIONAL')).toBe(false);
});

it('restores the unified task-center view while rejecting an unknown view', () => {
  expect(rememberLocalStudioResume('project-a', {
    module: 'ASSETS', view: 'TASKS', stage: 'M4', interfaceMode: 'NOVICE',
  })).toBe(true);
  expect(readLocalStudioResume('project-a')).toEqual({ state: 'SAVED', location: {
    module: 'ASSETS', view: 'TASKS', stage: 'M4', interfaceMode: 'NOVICE',
  } });
  expect(readLocalStudioResume('project-a', stored({ ...record, view: 'INBOX' }))).toEqual({ state: 'INVALID' });
});
