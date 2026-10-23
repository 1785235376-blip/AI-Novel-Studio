// @vitest-environment jsdom
// Browser recovery hints only. No HTTP, provider, execution or server canvas is represented.
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext, type CollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {canvasTaskBindingKey, captureCanvasTaskOwner, imageDraftNodeExists, readCanvasTaskBinding, subscribeCanvasTaskBindings, writeCanvasTaskBinding} from './canvasTaskBinding';

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
