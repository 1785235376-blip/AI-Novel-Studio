import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';

export type StyleDNALeaveOwner = {
  key: object;
  read: () => { dirty: boolean; busy: boolean; canSave: boolean; retired: boolean; revision: number };
  save: () => Promise<number | undefined>;
  discard: () => boolean;
};
export type StyleDNALeaveBridge = {
  generation?: number;
  register: (owner: StyleDNALeaveOwner) => () => void;
  changed: (key: object) => void;
  request: (action: (current: () => boolean) => void | Promise<void>, signal?: AbortSignal) => Promise<boolean>;
};
type Pending = { ticket: number; owner: StyleDNALeaveOwner; action: (current: () => boolean) => void | Promise<void>; finish: (value: boolean) => void; fail: (error: unknown) => void };

/** A leave gate for the original callbacks, never a router or a draft store. */
export function useStyleDNALeaveGuard(contextCurrent: () => boolean, identity: string) {
  const active = useRef<StyleDNALeaveOwner>();
  const pending = useRef<Pending>();
  const sequence = useRef(0), generation = useRef(0), alive = useRef(true);
  const live = useRef({ contextCurrent, identity }); live.current = { contextCurrent, identity };
  const [, render] = useState(0);
  const [message, setMessage] = useState('');
  const refresh = useCallback(() => { if (alive.current) render(value => value + 1); }, []);
  const cancel = useCallback(() => { sequence.current++; pending.current?.finish(false); pending.current = undefined; setMessage(''); refresh(); }, [refresh]);
  const retire = useCallback(() => { generation.current++; active.current = undefined; cancel(); }, [cancel]);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; pending.current?.finish(false); pending.current = undefined; active.current = undefined; }; }, []);
  const previousIdentity = useRef(identity);
  if (previousIdentity.current !== identity) { generation.current++; previousIdentity.current = identity; active.current = undefined; pending.current?.finish(false); pending.current = undefined; sequence.current++; }
  const register = useCallback((owner: StyleDNALeaveOwner) => {
    if (owner.read().retired || !live.current.contextCurrent()) return () => {};
    active.current = owner;
    sequence.current++; pending.current?.finish(false); pending.current = undefined; refresh();
    return () => { if (active.current?.key === owner.key) { active.current = undefined; sequence.current++; pending.current?.finish(false); pending.current = undefined; refresh(); } };
  }, [refresh]);
  const changed = useCallback((key: object) => {
    if (active.current?.key !== key) return;
    if (active.current.read().retired) { sequence.current++; pending.current?.finish(false); pending.current = undefined; }
    refresh();
  }, [refresh]);
  const request = useCallback<StyleDNALeaveBridge['request']>((action, signal) => new Promise<boolean>((resolve, reject) => {
    if (!alive.current || !live.current.contextCurrent() || signal?.aborted) { resolve(false); return; }
    const ticket = ++sequence.current, origin = live.current.identity, owner = active.current;
    const finish = (value: boolean) => { signal?.removeEventListener('abort', abort); resolve(value); };
    const fail = (error: unknown) => { signal?.removeEventListener('abort', abort); reject(error); };
    const abort = () => {
      if (sequence.current === ticket) { sequence.current++; pending.current = undefined; refresh(); }
      finish(false);
    };
    signal?.addEventListener('abort', abort, { once: true });
    pending.current?.finish(false); pending.current = undefined; setMessage('');
    const current = () => alive.current && !signal?.aborted && sequence.current === ticket && live.current.identity === origin && live.current.contextCurrent();
    if (owner && !owner.read().retired && (owner.read().dirty || owner.read().busy)) {
      pending.current = { ticket, owner, action, finish, fail }; refresh(); return;
    }
    refresh();
    try { Promise.resolve(action(current)).then(() => finish(true), fail); } catch (error) { fail(error); }
  }), [refresh]);
  const resolve = async (save: boolean) => {
    const intent = pending.current;
    if (!intent) return;
    const origin = live.current.identity;
    const current = () => alive.current && sequence.current === intent.ticket && active.current?.key === intent.owner.key
      && live.current.identity === origin && live.current.contextCurrent() && !intent.owner.read().retired;
    if (!current() || intent.owner.read().busy) return;
    if (save && intent.owner.read().dirty) {
      if (!intent.owner.read().canSave) return;
      const revision = intent.owner.read().revision;
      let saved: number | undefined;
      try { saved = await intent.owner.save(); } catch { /* The editor owns detailed errors and private values. */ }
      if (!current()) return;
      if (saved !== revision || intent.owner.read().dirty || intent.owner.read().busy) {
        setMessage('Style DNA 尚未确认保存，输入已保留。请核对错误或版本后重试。'); refresh(); return;
      }
    } else if (!save && intent.owner.read().dirty && !intent.owner.discard()) return;
    if (!current()) return;
    pending.current = undefined; refresh();
    try { await intent.action(current); intent.finish(true); } catch (error) { intent.fail(error); }
  };
  const state = pending.current?.owner.read();
  const dialog = pending.current && state && !state.retired ? <Panel title="离开 Style DNA 编辑器" role="region" aria-label="Style DNA 未保存修改">
    <StatusMessage tone="warning">Style DNA 有未保存修改。保存后离开、放弃本地修改，或继续编辑。取消离开不会取消已经发出的保存。</StatusMessage>
    {message && <StatusMessage tone="error">{message}</StatusMessage>}
    <div className="experimental-actions">
      <Button disabled={state.busy || !state.canSave} onClick={() => void resolve(true)}>保存 Style DNA 后离开</Button>
      <Button disabled={state.busy} onClick={() => void resolve(false)}>放弃 Style DNA 修改并离开</Button>
      <Button onClick={cancel}>继续编辑 Style DNA</Button>
    </div>
  </Panel> : null;
  return { register, changed, request, retire, dialog, generation: generation.current };
}
