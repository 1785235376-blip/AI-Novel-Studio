// @vitest-environment jsdom
// Browser recovery hints only. No HTTP, provider, execution or server canvas is represented.
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationEpoch, setCollaborationContext, type CollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {canvasTaskBindingKey, captureCanvasTaskOwner, imageDraftNodeExists, readCanvasTaskBinding, subscribeCanvasTaskBindings, writeCanvasTaskAdoption, writeCanvasTaskBinding, type CanvasTaskAdoption} from './canvasTaskBinding';

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
    expect(JSON.parse(raw)).toEqual({schema_version: 1, owner, nodeId, taskId: 'server-task-1'});
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
      expect(JSON.parse(raw)).toEqual({...binding, adoption});
      expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual({...binding, adoption});
      expect(raw).not.toMatch(/prompt|status|approval|sessionToken|sourceUri|blob:|https:|not-persisted-session-secret|loaded|confirmed/);
      expect(fetcher).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });

  it('keeps old four-field bindings readable and clears the asset association on an explicit new-task binding', () => {
    const binding = linkedTask();
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual(binding);
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(true);
    expect(writeCanvasTaskBinding(binding.owner, nodeId, 'new-server-task')).toBe(true);
    expect(readCanvasTaskBinding(binding.owner, nodeId)).toEqual({...binding, taskId: 'new-server-task'});
    expect(localStorage.getItem(canvasTaskBindingKey(binding.owner, nodeId))).not.toContain('adoption');
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
    expect(writeCanvasTaskAdoption(binding, adoption, () => true)).toBe(true);
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
