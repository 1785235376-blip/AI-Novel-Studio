// @vitest-environment jsdom
// Browser recovery hints only. No HTTP, provider, execution or server canvas is represented.
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationEpoch, setCollaborationContext, type CollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {canvasTaskBindingKey, captureCanvasTaskOwner, imageDraftNodeExists, MAX_CANVAS_TASK_HISTORY, readCanvasTaskBinding, restoreCanvasTaskAdoption, subscribeCanvasTaskBindings, writeCanvasTaskAdoption, writeCanvasTaskBinding, type CanvasTaskAdoption, type CanvasTaskBinding, type CanvasTaskHistoryEntry} from './canvasTaskBinding';

const novelId = 'binding-project', nodeId = 'original-image-node';
const context = (branchId = 'branch-a'): CollaborationContext => ({sessionToken: 'not-persisted-session-secret',
  actor: {id: 'binding-author', workspaceId: 'binding-workspace', displayName: 'Author'},
  scope: {workspaceId: 'binding-workspace', projectId: novelId, storylineId: 'storyline-a', branchId}});
const graph = (nodes: unknown[] = [{id: nodeId, t: 'image_generate', prompt: 'Original draft'}]) => localStorage.setItem(canvasStorageKey('image', novelId), JSON.stringify({nodes, edges: []}));
beforeEach(() => { localStorage.clear(); setCollaborationContext(context()); useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); graph(); });
afterEach(() => { vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); });

describe('browser image node task navigation binding', () => {
  it('persists only the original server task ID and non-secret owner, then reopens exactly that hint', () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    expect(writeCanvasTaskBinding(owner, nodeId, 'server-task-1')).toBe(true);
    const raw = localStorage.getItem(canvasTaskBindingKey(owner, nodeId))!;
    expect(JSON.parse(raw)).toEqual({schema_version: 2, owner, nodeId, taskId: 'server-task-1', revision: 1,
      history: [{eventId: expect.any(String), revision: 1, operation: 'queue', taskId: 'server-task-1'}]});
    expect(raw).not.toContain('not-persisted-session-secret');
    expect(raw).not.toContain('Original draft');
    expect(raw).not.toMatch(/status|QUEUED|allow_cloud|provider|model/);
    expect(readCanvasTaskBinding(captureCanvasTaskOwner(novelId)!, nodeId)?.taskId).toBe('server-task-1');
  });

  it('requires complete collaboration scope and a matching project/workspace', () => {
    const good = context();
    for (const bad of [{...good, sessionToken: ''}, {...good, actor: undefined}, {...good, scope: undefined},
      {...good, actor: {...good.actor!, workspaceId: 'other-workspace'}},
      {...good, scope: {...good.scope!, projectId: 'other-project'}}, {...good, scope: {...good.scope!, storylineId: ''}}]) {
      setCollaborationContext(bad);
      expect(captureCanvasTaskOwner(novelId)).toBeUndefined();
    }
  });

  it('does not give anonymous callers a durable owner; verified local Host survives a token rotation as the same actor', () => {
    setCollaborationContext({sessionToken: ''});
    expect(captureCanvasTaskOwner(novelId)).toBeUndefined();
    bindLocalHostSession('not-persisted-local-secret', {session_mode: 'LOCAL_HOST', actor_id: 'local-author'});
    const owner = captureCanvasTaskOwner(novelId)!;
    expect(owner.mode).toBe('local');
    expect(writeCanvasTaskBinding(owner, nodeId, 'local-server-task')).toBe(true);
    expect(localStorage.getItem(canvasTaskBindingKey(owner, nodeId))).not.toContain('not-persisted-local-secret');
    bindLocalHostSession('rotated-local-secret', {session_mode: 'LOCAL_HOST', actor_id: 'local-author'});
    expect(readCanvasTaskBinding(captureCanvasTaskOwner(novelId)!, nodeId)?.taskId).toBe('local-server-task');
    setCollaborationContext({sessionToken: '', localHostToken: 'not-the-verified-host'});
    expect(captureCanvasTaskOwner(novelId)).toBeUndefined();
  });

  it('isolates actor, workspace, storyline, branch and project owners', () => {
    const original = captureCanvasTaskOwner(novelId)!;
    expect(writeCanvasTaskBinding(original, nodeId, 'private-server-task')).toBe(true);
    const good = context();
    for (const next of [context('branch-b'), {...good, actor: {...good.actor!, id: 'other-author'}},
      {...good, actor: {...good.actor!, workspaceId: 'other-workspace'}, scope: {...good.scope!, workspaceId: 'other-workspace'}},
      {...good, scope: {...good.scope!, storylineId: 'other-storyline'}}]) {
      setCollaborationContext(next);
      const owner = captureCanvasTaskOwner(novelId)!;
      expect(readCanvasTaskBinding(owner, nodeId)).toBeUndefined();
      expect(readCanvasTaskBinding(original, nodeId)).toBeUndefined();
      expect(writeCanvasTaskBinding(original, nodeId, 'wrong-owner-task')).toBe(false);
    }
    setCollaborationContext({...good, scope: {...good.scope!, projectId: 'other-project'}});
    expect(captureCanvasTaskOwner(novelId)).toBeUndefined();
    setCollaborationContext(good);
    expect(readCanvasTaskBinding(original, nodeId)?.taskId).toBe('private-server-task');
  });

  it('requires the unique original image_generate node and never guesses a reference or replacement node', () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    for (const nodes of [[], [{id: nodeId, t: 'image_reference'}], [{id: 'replacement', t: 'image_generate'}],
      [{id: nodeId, t: 'image_generate'}, {id: nodeId, t: 'image_generate'}]]) {
      graph(nodes);
      expect(imageDraftNodeExists(novelId, nodeId)).toBe(false);
      expect(writeCanvasTaskBinding(owner, nodeId, 'server-task-1')).toBe(false);
    }
    graph();
    expect(writeCanvasTaskBinding(owner, nodeId, 'server-task-1')).toBe(true);
    graph([]);
    expect(readCanvasTaskBinding(owner, nodeId)).toBeUndefined();
  });

  it('preserves the historical task navigation hint after a prompt edit without persisting that prompt or a status', () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    writeCanvasTaskBinding(owner, nodeId, 'original-server-task');
    graph([{id: nodeId, t: 'image_generate', prompt: 'Different current prompt'}]);
    expect(readCanvasTaskBinding(owner, nodeId)?.taskId).toBe('original-server-task');
    expect(localStorage.getItem(canvasTaskBindingKey(owner, nodeId))).not.toContain('Different current prompt');
  });

  it('rejects malformed, oversized, wrong-owner and unknown-field records rather than trusting cached data', () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    const valid = {schema_version: 1, owner, nodeId, taskId: 'server-task-1'};
    for (const raw of ['invalid-json', ' '.repeat(8_001), JSON.stringify({...valid, schema_version: 2}),
      JSON.stringify({...valid, owner: {...owner, branchId: 'other-branch'}}), JSON.stringify({...valid, nodeId: 'other-node'}),
      JSON.stringify({...valid, taskId: 'https://invalid.example/task'}), JSON.stringify({...valid, status: 'SUCCEEDED'}),
      JSON.stringify({...valid, owner: {...owner, sessionToken: 'untrusted-extra-secret'}})]) {
      localStorage.setItem(canvasTaskBindingKey(owner, nodeId), raw);
      expect(readCanvasTaskBinding(owner, nodeId)).toBeUndefined();
    }
    expect(writeCanvasTaskBinding(owner, nodeId, 'javascript:untrusted')).toBe(false);
  });

  it('reports storage failure without claiming persistence or notifying listeners', () => {
    const owner = captureCanvasTaskOwner(novelId)!, listener = vi.fn();
    const unsubscribe = subscribeCanvasTaskBindings(listener);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError'); });
    expect(writeCanvasTaskBinding(owner, nodeId, 'server-task-1')).toBe(false);
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });

  it('requires read-after-write confirmation before claiming a hint was saved', () => {
    const owner = captureCanvasTaskOwner(novelId)!, listener = vi.fn();
    const unsubscribe = subscribeCanvasTaskBindings(listener);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
    expect(writeCanvasTaskBinding(owner, nodeId, 'server-task-1')).toBe(false);
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });

  it('notifies same-tab and relevant external storage changes, and stops after unsubscribe', () => {
    const owner = captureCanvasTaskOwner(novelId)!, listener = vi.fn();
    const unsubscribe = subscribeCanvasTaskBindings(listener);
    writeCanvasTaskBinding(owner, nodeId, 'server-task-1');
    expect(listener).toHaveBeenCalledTimes(1);
    window.dispatchEvent(new StorageEvent('storage', {key: canvasTaskBindingKey(owner, nodeId)}));
    window.dispatchEvent(new StorageEvent('storage', {key: canvasStorageKey('image', novelId)}));
    window.dispatchEvent(new StorageEvent('storage', {key: 'unrelated-storage-key'}));
    expect(listener).toHaveBeenCalledTimes(3);
    unsubscribe();
    writeCanvasTaskBinding(owner, nodeId, 'server-task-2');
    expect(listener).toHaveBeenCalledTimes(3);
  });
});

describe('explicit browser-local approved asset association', () => {
  const adoption: CanvasTaskAdoption = {assetId: 'original-approved-asset', assetVersion: 3,
    assetSha256: 'a'.repeat(64), jobObservationSha256: 'b'.repeat(64)};
  const linkedTask = () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    expect(writeCanvasTaskBinding(owner, nodeId, 'original-server-task')).toBe(true);
    return readCanvasTaskBinding(owner, nodeId)!;
  };

  it('stores the checked IDs and actual metadata pins in the original binding key without approval, preview or credential state', () => {
    const binding = linkedTask(), current = vi.fn(() => true), fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    try {
      expect(writeCanvasTaskAdoption(binding, adoption, current)).toBe(true);
      expect(current).toHaveBeenCalledTimes(2);
      const raw = localStorage.getItem(canvasTaskBindingKey(binding.owner, nodeId))!;
      expect(JSON.parse(raw)).toEqual({...binding, adoption, revision: 2,
        history: [...binding.history!, {eventId: expect.any(String), revision: 2, operation: 'adopt', taskId: binding.taskId, adoption}]});
      expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual(JSON.parse(raw));
      expect(raw).not.toMatch(/prompt|status|approval|sessionToken|sourceUri|blob:|https:|not-persisted-session-secret|loaded|confirmed/);
      expect(fetcher).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });

  it('keeps old four-field bindings readable and clears the asset association on an explicit new-task binding', () => {
    const binding: CanvasTaskBinding = {schema_version: 1, owner: captureCanvasTaskOwner(novelId)!, nodeId, taskId: 'original-server-task'};
    localStorage.setItem(canvasTaskBindingKey(binding.owner, nodeId), JSON.stringify(binding));
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual(binding);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(true);
    expect(writeCanvasTaskBinding(binding.owner, nodeId, 'new-server-task')).toBe(true);
    const current = readCanvasTaskBinding(binding.owner, nodeId)!;
    expect(current.taskId).toBe('new-server-task');
    expect(current.adoption).toBeUndefined();
    expect(current.history?.map(entry => entry.operation)).toEqual(['import', 'adopt', 'queue']);
    expect(current.history?.[1].adoption).toEqual(adoption);
  });

  it.each([
    {assetId: 'https://untrusted.invalid/asset'}, {assetId: ''}, {assetVersion: 0}, {assetVersion: -1},
    {assetVersion: 1.5}, {assetVersion: Number.MAX_SAFE_INTEGER + 1}, {assetVersion: '3'},
    {assetSha256: 'not-the-actual-byte-hash'}, {assetSha256: 'A'.repeat(64)}, {jobObservationSha256: 'missing'},
    {approvalStatus: 'APPROVED'}, {sourceUri: 'https://untrusted.invalid/signed-candidate'},
  ])('rejects malformed or surplus asset association fields on write and read: %j', change => {
    const binding = linkedTask(), invalid = {...adoption, ...change};
    expect(writeCanvasTaskAdoption(binding, invalid as CanvasTaskAdoption, () => true)).toBe(false);
    localStorage.setItem(canvasTaskBindingKey(binding.owner, nodeId), JSON.stringify({...binding, adoption: invalid}));
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toBeUndefined();
  });

  it('rejects an absent/null asset association and a non-v1 or surplus outer schema rather than restoring confirmation state', () => {
    const binding = linkedTask();
    for (const record of [{...binding, adoption: null}, {...binding, adoption: {}}, {...binding, adoption, schema_version: 2},
      {...binding, adoption, confirmed: true}, {...binding, adoption: {...adoption, imageLoaded: true}}]) {
      localStorage.setItem(canvasTaskBindingKey(binding.owner, nodeId), JSON.stringify(record));
      expect(readCanvasTaskBinding(binding.owner, nodeId)).toBeUndefined();
      expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    }
  });

  it('compares the original task and every existing asset pin before updating the association', () => {
    const binding = linkedTask();
    expect(writeCanvasTaskBinding(binding.owner, nodeId, 'replacement-server-task')).toBe(true);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    expect(writeCanvasTaskBinding(binding.owner, nodeId, binding.taskId)).toBe(true);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    expect(writeCanvasTaskAdoption(readCanvasTaskBinding(binding.owner, nodeId)!, adoption, () => true)).toBe(true);
    // A ticket from before the first explicit association cannot replace that association.
    expect(writeCanvasTaskAdoption(binding, {...adoption, assetId: 'other-approved-asset'}, () => true)).toBe(false);
    const observed = readCanvasTaskBinding(binding.owner, nodeId)!;
    for (const change of [{assetId: 'other-approved-asset'}, {assetVersion: 4}, {assetSha256: 'c'.repeat(64)}, {jobObservationSha256: 'd'.repeat(64)}]) {
      const changed = {...observed, adoption: {...adoption, ...change}};
      localStorage.setItem(canvasTaskBindingKey(binding.owner, nodeId), JSON.stringify(changed));
      expect(writeCanvasTaskAdoption(observed, adoption, () => true)).toBe(false);
    }
  });

  it('requires the current original owner and node even when a stale caller supplies a true fence', () => {
    const binding = linkedTask();
    setCollaborationContext(context('other-branch'));
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    setCollaborationContext(context());
    graph([]);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    graph([{id: nodeId, t: 'image_reference'}]);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
  });

  it('honors the caller fence after identity and prompt A/B/A transitions without copying their details into the cache', () => {
    const binding = linkedTask(), epoch = getCollaborationEpoch();
    setCollaborationContext(context('temporary-branch'));
    setCollaborationContext(context());
    expect(writeCanvasTaskAdoption(binding, adoption, () => getCollaborationEpoch() === epoch)).toBe(false);
    let sourceRevision = 1;
    const capturedRevision = sourceRevision;
    graph([{id: nodeId, t: 'image_generate', prompt: 'Temporary draft'}]); sourceRevision += 1;
    graph(); sourceRevision += 1;
    expect(writeCanvasTaskAdoption(binding, adoption, () => sourceRevision === capturedRevision)).toBe(false);
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual(binding);
  });

  it('checks the observation/source fence again immediately before writing and fails closed if that check throws', () => {
    const binding = linkedTask(), expired = vi.fn().mockReturnValueOnce(true).mockReturnValue(false);
    expect(writeCanvasTaskAdoption(binding, adoption, expired)).toBe(false);
    expect(expired).toHaveBeenCalledTimes(2);
    expect(writeCanvasTaskAdoption(binding, adoption, () => { throw new Error('Retired source'); })).toBe(false);
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual(binding);
  });

  it('does not report success or notify observers if storage throws or the written record cannot be confirmed', () => {
    const binding = linkedTask(), listener = vi.fn(), unsubscribe = subscribeCanvasTaskBindings(listener);
    const setter = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError'); });
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    expect(listener).not.toHaveBeenCalled();
    setter.mockImplementation(() => {});
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(false);
    expect(listener).not.toHaveBeenCalled();
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual(binding);
    unsubscribe();
  });

  it('notifies only after successful read-after-write confirmation and returns defensive copies on reopen', () => {
    const binding = linkedTask(), listener = vi.fn(), unsubscribe = subscribeCanvasTaskBindings(listener);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);
    const reopened = readCanvasTaskBinding(binding.owner, nodeId)!;
    reopened.adoption!.assetId = 'not-the-stored-asset';
    expect(readCanvasTaskBinding(binding.owner, nodeId)?.adoption).toEqual(adoption);
    unsubscribe();
  });
});

describe('bounded browser task association journal and explicit restore', () => {
  const firstPin: CanvasTaskAdoption = {assetId: 'first-approved-asset', assetVersion: 1,
    assetSha256: 'a'.repeat(64), jobObservationSha256: 'b'.repeat(64)};
  const secondPin: CanvasTaskAdoption = {assetId: 'second-approved-asset', assetVersion: 4,
    assetSha256: 'c'.repeat(64), jobObservationSha256: 'd'.repeat(64)};
  const latest = () => readCanvasTaskBinding(captureCanvasTaskOwner(novelId)!, nodeId)!;
  const journal = () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    expect(writeCanvasTaskBinding(owner, nodeId, 'first-server-task')).toBe(true);
    expect(writeCanvasTaskAdoption(latest(), firstPin, () => true)).toBe(true);
    expect(writeCanvasTaskBinding(owner, nodeId, 'second-server-task')).toBe(true);
    expect(writeCanvasTaskAdoption(latest(), secondPin, () => true)).toBe(true);
    return latest();
  };
  const storedRaw = (binding: CanvasTaskBinding) => localStorage.getItem(canvasTaskBindingKey(binding.owner, nodeId));

  it.each([false, true])('reads a valid legacy record without mutation, then imports its observed state once (has pin: %s)', hasPin => {
    const legacy: CanvasTaskBinding = {schema_version: 1, owner: captureCanvasTaskOwner(novelId)!, nodeId,
      taskId: 'legacy-server-task', ...(hasPin ? {adoption: firstPin} : {})};
    const raw = JSON.stringify(legacy);
    localStorage.setItem(canvasTaskBindingKey(legacy.owner, nodeId), raw);
    expect(latest()).toEqual(legacy);
    expect(storedRaw(legacy)).toBe(raw);
    expect(writeCanvasTaskBinding(legacy.owner, nodeId, 'new-server-task')).toBe(true);
    const next = latest();
    expect(next.schema_version).toBe(2);
    expect(next.revision).toBe(2);
    expect(next.history).toEqual([
      {eventId: expect.any(String), revision: 1, operation: 'import', taskId: legacy.taskId, ...(hasPin ? {adoption: firstPin} : {})},
      {eventId: expect.any(String), revision: 2, operation: 'queue', taskId: 'new-server-task'},
    ]);
    expect(next.adoption).toBeUndefined();
    expect(storedRaw(next)).not.toMatch(/timestamp|saved_at|approved_at|adopted_at|imported_at|Date|prompt|sessionToken|sourceUri/);
    expect(writeCanvasTaskAdoption(next, secondPin, () => true)).toBe(true);
    expect(latest().history?.filter(entry => entry.operation === 'import')).toHaveLength(1);
  });

  it('preserves a legacy asset pin as an import when the first journal mutation is a new explicit adoption', () => {
    const legacy: CanvasTaskBinding = {schema_version: 1, owner: captureCanvasTaskOwner(novelId)!, nodeId,
      taskId: 'legacy-server-task', adoption: firstPin};
    localStorage.setItem(canvasTaskBindingKey(legacy.owner, nodeId), JSON.stringify(legacy));
    expect(writeCanvasTaskAdoption(legacy, secondPin, () => true)).toBe(true);
    expect(latest().history?.map(entry => ({operation: entry.operation, adoption: entry.adoption}))).toEqual([
      {operation: 'import', adoption: firstPin}, {operation: 'adopt', adoption: secondPin},
    ]);
  });

  it('appends queue, adoption and restore records, preserving every earlier valid record and the exact source', () => {
    const before = journal(), source = before.history![1], snapshot = structuredClone(before.history);
    expect(restoreCanvasTaskAdoption(before, source, firstPin, () => true)).toBe(true);
    const restored = latest();
    expect(restored.taskId).toBe('first-server-task');
    expect(restored.adoption).toEqual(firstPin);
    expect(restored.revision).toBe(5);
    expect(restored.history?.slice(0, -1)).toEqual(snapshot);
    expect(restored.history?.[4]).toEqual({eventId: expect.any(String), revision: 5, operation: 'restore',
      taskId: source.taskId, adoption: firstPin, sourceEventId: source.eventId});
    expect(before.history).toEqual(snapshot);
    expect(new Set(restored.history?.map(entry => entry.eventId)).size).toBe(restored.history?.length);
    expect(writeCanvasTaskBinding(restored.owner, nodeId, 'third-server-task')).toBe(true);
    expect(latest().history?.slice(0, -1)).toEqual(restored.history);
    expect(latest().adoption).toBeUndefined();
  });

  it('can restore a prior restore record as a fresh append, without editing or reusing that event', () => {
    const initial = journal(), original = initial.history![1], other = initial.history![3];
    expect(restoreCanvasTaskAdoption(initial, original, firstPin, () => true)).toBe(true);
    const firstRestore = latest().history![4];
    expect(restoreCanvasTaskAdoption(latest(), other, secondPin, () => true)).toBe(true);
    expect(restoreCanvasTaskAdoption(latest(), firstRestore, firstPin, () => true)).toBe(true);
    const current = latest();
    expect(current.revision).toBe(7);
    expect(current.history?.[6].sourceEventId).toBe(firstRestore.eventId);
    expect(current.history?.[6].eventId).not.toBe(firstRestore.eventId);
  });

  it.each([
    {assetId: 'different-asset'}, {assetVersion: 2}, {assetSha256: 'e'.repeat(64)}, {jobObservationSha256: 'f'.repeat(64)},
  ])('requires every freshly checked target pin to equal its historical observation: %j', change => {
    const current = journal(), source = current.history![1], raw = storedRaw(current);
    expect(restoreCanvasTaskAdoption(current, source, {...firstPin, ...change}, () => true)).toBe(false);
    expect(storedRaw(current)).toBe(raw);
  });

  it('rejects unknown or changed source entries, unpinned queue entries, and a restore of the current task/pin', () => {
    const current = journal(), source = current.history![1], raw = storedRaw(current);
    for (const target of [{...source, eventId: 'not-in-the-journal'}, {...source, revision: 99},
      {...source, operation: 'import' as const}, {...source, taskId: 'foreign-task'},
      {...source, adoption: {...firstPin, assetVersion: 2}}, {...source, unrecognized: undefined}, {...source, sourceEventId: undefined}, current.history![0], current.history![3]]) {
      expect(restoreCanvasTaskAdoption(current, target, target.adoption || firstPin, () => true)).toBe(false);
    }
    expect(storedRaw(current)).toBe(raw);
  });

  it('rejects old adoption and restore tickets after a full task/pin A/B/A round trip', () => {
    const original = journal(), first = original.history![1], second = original.history![3];
    expect(restoreCanvasTaskAdoption(original, first, firstPin, () => true)).toBe(true);
    expect(restoreCanvasTaskAdoption(latest(), second, secondPin, () => true)).toBe(true);
    const current = latest(), raw = storedRaw(current);
    expect(current.taskId).toBe(original.taskId);
    expect(current.adoption).toEqual(original.adoption);
    expect(current.revision).toBeGreaterThan(original.revision!);
    expect(writeCanvasTaskAdoption(original, secondPin, () => true)).toBe(false);
    expect(restoreCanvasTaskAdoption(original, first, firstPin, () => true)).toBe(false);
    expect(storedRaw(current)).toBe(raw);
  });

  it('compares the entire prior journal, not only its revision and current head', () => {
    const original = journal(), changed = structuredClone(original);
    changed.history![0].eventId = 'changed-but-structurally-valid-event';
    localStorage.setItem(canvasTaskBindingKey(original.owner, nodeId), JSON.stringify(changed));
    expect(latest()).toEqual(changed);
    expect(writeCanvasTaskAdoption(original, secondPin, () => true)).toBe(false);
    expect(restoreCanvasTaskAdoption(original, original.history![1], firstPin, () => true)).toBe(false);
    expect(latest()).toEqual(changed);
  });

  it('rejects all writes at capacity without pruning any valid history, including journals larger than the old 8KB limit', () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    const entries: CanvasTaskHistoryEntry[] = Array.from({length: MAX_CANVAS_TASK_HISTORY}, (_, index) => ({
      eventId: `event-${index}-${'e'.repeat(200)}`, revision: index + 1, operation: 'queue', taskId: `task-${index}-${'t'.repeat(200)}`,
    }));
    entries[1] = {...entries[1], operation: 'adopt', taskId: entries[0].taskId, adoption: firstPin};
    const full: CanvasTaskBinding = {schema_version: 2, owner, nodeId, taskId: entries.at(-1)!.taskId,
      revision: MAX_CANVAS_TASK_HISTORY, history: entries};
    const raw = JSON.stringify(full);
    expect(raw.length).toBeGreaterThan(8_000);
    localStorage.setItem(canvasTaskBindingKey(owner, nodeId), raw);
    expect(latest()).toEqual(full);
    expect(writeCanvasTaskBinding(owner, nodeId, 'next-task')).toBe(false);
    expect(writeCanvasTaskAdoption(full, secondPin, () => true)).toBe(false);
    expect(restoreCanvasTaskAdoption(full, entries[1], firstPin, () => true)).toBe(false);
    expect(storedRaw(full)).toBe(raw);
  });

  const corruptions: {label: string; mutate: (binding: CanvasTaskBinding) => void}[] = [
    {label: 'duplicate event ID', mutate: binding => { binding.history![1].eventId = binding.history![0].eventId; }},
    {label: 'revision gap', mutate: binding => { binding.history![1].revision = 3; }},
    {label: 'head revision mismatch', mutate: binding => { binding.revision = 99; }},
    {label: 'unknown entry field', mutate: binding => { Object.assign(binding.history![0], {prompt: 'must-not-be-in-journal'}); }},
    {label: 'empty history', mutate: binding => { binding.history = []; binding.revision = 0; }},
    {label: 'unknown operation', mutate: binding => { Object.assign(binding.history![0], {operation: 'server-approved'}); }},
    {label: 'import after first entry', mutate: binding => { binding.history![1].operation = 'import'; }},
    {label: 'adopt as the first entry', mutate: binding => { Object.assign(binding.history![0], {operation: 'adopt', adoption: firstPin}); }},
    {label: 'adopt without pin', mutate: binding => { delete binding.history![1].adoption; }},
    {label: 'adopt on a different task', mutate: binding => { binding.history![1].taskId = 'different-task'; }},
    {label: 'queue with an asset pin', mutate: binding => { binding.history![0].adoption = firstPin; }},
    {label: 'queue with a restore source', mutate: binding => { binding.history![0].sourceEventId = 'some-source'; }},
    {label: 'unknown restore source', mutate: binding => { binding.history![4].sourceEventId = 'not-in-history'; }},
    {label: 'self restore source', mutate: binding => { binding.history![4].sourceEventId = binding.history![4].eventId; }},
    {label: 'restore without pin', mutate: binding => { delete binding.history![4].adoption; }},
    {label: 'restore pin differs from source', mutate: binding => { binding.history![4].adoption = secondPin; }},
    {label: 'restore task differs from source', mutate: binding => { binding.history![4].taskId = 'different-task'; }},
    {label: 'head task differs from tail', mutate: binding => { binding.taskId = 'different-head-task'; }},
    {label: 'head pin differs from tail', mutate: binding => { binding.adoption = secondPin; }},
  ];
  it.each(corruptions)('fails closed on $label and never overwrites that unreadable record', ({mutate}) => {
    const original = journal(), source = original.history![1];
    expect(restoreCanvasTaskAdoption(original, source, firstPin, () => true)).toBe(true);
    const valid = latest(), invalid = structuredClone(valid);
    mutate(invalid);
    const raw = JSON.stringify(invalid);
    localStorage.setItem(canvasTaskBindingKey(valid.owner, nodeId), raw);
    expect(readCanvasTaskBinding(valid.owner, nodeId)).toBeUndefined();
    expect(writeCanvasTaskBinding(valid.owner, nodeId, 'do-not-overwrite')).toBe(false);
    expect(writeCanvasTaskAdoption(valid, secondPin, () => true)).toBe(false);
    expect(restoreCanvasTaskAdoption(valid, source, firstPin, () => true)).toBe(false);
    expect(storedRaw(valid)).toBe(raw);
  });

  it('does not overwrite malformed JSON or an empty existing record as though no prior history existed', () => {
    const owner = captureCanvasTaskOwner(novelId)!;
    for (const raw of ['', '{broken-json']) {
      localStorage.setItem(canvasTaskBindingKey(owner, nodeId), raw);
      expect(writeCanvasTaskBinding(owner, nodeId, 'do-not-overwrite')).toBe(false);
      expect(localStorage.getItem(canvasTaskBindingKey(owner, nodeId))).toBe(raw);
    }
  });

  it('requires current owner/source and final caller fence for restore, with no success on quota/readback failure', () => {
    const original = journal(), source = original.history![1], raw = storedRaw(original);
    setCollaborationContext(context('other-branch'));
    expect(restoreCanvasTaskAdoption(original, source, firstPin, () => true)).toBe(false);
    setCollaborationContext(context());
    const expired = vi.fn().mockReturnValueOnce(true).mockReturnValue(false);
    expect(restoreCanvasTaskAdoption(original, source, firstPin, expired)).toBe(false);
    expect(expired).toHaveBeenCalledTimes(2);
    expect(restoreCanvasTaskAdoption(original, source, firstPin, () => { throw new Error('Retired prompt'); })).toBe(false);
    const setter = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError'); });
    expect(restoreCanvasTaskAdoption(original, source, firstPin, () => true)).toBe(false);
    setter.mockImplementation(() => {});
    expect(restoreCanvasTaskAdoption(original, source, firstPin, () => true)).toBe(false);
    expect(storedRaw(original)).toBe(raw);
  });

  it('returns independent history copies and does not reuse a source event as a new restore event', () => {
    const original = journal(), reopened = latest();
    reopened.history![1].adoption!.assetId = 'not-the-stored-asset';
    reopened.history!.push({eventId: 'not-stored', revision: 5, operation: 'queue', taskId: 'not-stored'});
    expect(latest()).toEqual(original);
    const source = original.history![1];
    expect(restoreCanvasTaskAdoption(original, source, firstPin, () => true)).toBe(true);
    expect(latest().history![4].eventId).not.toBe(source.eventId);
  });
});
