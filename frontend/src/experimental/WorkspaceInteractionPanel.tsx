import { useEffect, useMemo, useRef, useState } from 'react';
import type { ExperimentalClient } from './api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Field, ResourceState, useAction, useResource } from './shared';

type Preferences = { keyboard_enabled: boolean; shortcuts: Record<string, string>; announcements: 'polite' | 'off'; reduced_motion: 'system' | 'reduce'; confirm_navigation_with_unsaved_input: true };
type Profile = { version: number; preferences: Preferences; state: string; recovery_required: boolean };
type Command = { id: string; section: string; label: string; shortcut: string | null };
type Commands = { revision: string; state: string; preferences_version: number; items: Command[] };
type Target = { kind: 'workspace_section'; section: string; command_id: string; requires_dirty_guard: true; dispatched: false };
export function interactionClient(client: ExperimentalClient) {
  const base = '/workspace';
  return {
    read: (signal?: AbortSignal) => client.get<Profile>(base + '/interaction', signal),
    save: (version: number, preferences: Preferences) => client.put<Profile>(base + '/interaction', { expected_version: version, preferences }),
    reset: (version: number) => client.post<Profile>(base + '/interaction/reset', { expected_version: version }),
    history: (signal?: AbortSignal) => client.get<{ items: { version: number; state: string }[] }>(base + '/interaction/history', signal),
    restore: (version: number, sourceVersion: number) => client.post<Profile>(base + '/interaction/restore', { expected_version: version, source_version: sourceVersion }),
    commands: (signal?: AbortSignal) => client.get<Commands>(base + '/commands', signal),
    resolve: (command: Command, revision: string) => client.post<Target>(base + '/commands/resolve', { command_id: command.id, expected_revision: revision }),
  };
}

function shortcut(event: KeyboardEvent): string | null {
  if (event.defaultPrevented || event.isComposing || event.repeat || event.altKey || !event.shiftKey || !(event.ctrlKey || event.metaKey)) return null;
  if (event.ctrlKey && event.metaKey) return null;
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest('input, textarea, select, [contenteditable="true"], [role="textbox"]')) return null;
  return 'Mod+Shift+' + event.key.toUpperCase();
}

export function WorkspaceInteractionPanel({ client, dirty, currentSection, onSection }: { client: ExperimentalClient; dirty: boolean; currentSection: string; onSection: (section: string) => void }) {
  const api = useMemo(() => interactionClient(client), [client]);
  const profile = useResource(signal => api.read(signal), [api]);
  const commands = useResource(signal => api.commands(signal), [api, profile.data?.version]);
  const history = useResource(signal => api.history(signal), [api, profile.data?.version]);
  const action = useAction();
  const host = useRef<HTMLDivElement>(null);
  const alive = useRef(true), epoch = useRef(0), resolving = useRef(false);
  const latest = useRef({ dirty, onSection }); latest.current = { dirty, onSection };
  const [draft, setDraft] = useState<Preferences>();
  const [saved, setSaved] = useState<Profile>();
  const [pending, setPending] = useState<Command>();
  const [notice, setNotice] = useState('');
  const touched = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { epoch.current++; setPending(undefined); }, [currentSection]);
  useEffect(() => {
    if (profile.data) { setSaved(profile.data); if (!touched.current) setDraft(profile.data.preferences); }
  }, [profile.data]);
  const publish = (value: Profile) => {
    if (!alive.current) return;
    touched.current = false; setSaved(value); setDraft(value.preferences); setPending(undefined); profile.reload();
  };
  const hasDraft = Boolean(draft && saved && JSON.stringify(draft) !== JSON.stringify(saved.preferences));
  const enter = async (command: Command, confirmed = false) => {
    if (resolving.current || !commands.data || commands.loading || commands.error || profile.error) return;
    if (!confirmed && (latest.current.dirty || hasDraft)) { setPending(command); return; }
    resolving.current = true;
    const ticket = ++epoch.current;
    try {
      const result = await api.resolve(command, commands.data.revision);
      if (!alive.current || ticket !== epoch.current) return;
      setPending(undefined);
      latest.current.onSection(result.section);
      setNotice('已切换到' + command.label + '。未提交任何任务。');
    } catch {
      if (alive.current && ticket === epoch.current) {
        setPending(undefined); setNotice('命令状态已变化或当前无权访问，请重新核对。'); commands.reload();
      }
    } finally { resolving.current = false; }
  };
  const enterRef = useRef(enter); enterRef.current = enter;
  useEffect(() => {
    const root = host.current?.closest('section[aria-label="工作现场工具"]');
    if (!root || !commands.data || commands.error || commands.loading || profile.error || profile.loading) return;
    const handle = (raw: Event) => {
      const event = raw as KeyboardEvent;
      const key = shortcut(event);
      const command = key && commands.data?.items.find(row => row.shortcut === key);
      if (!command) return;
      event.preventDefault(); void enterRef.current(command);
    };
    root.addEventListener('keydown', handle);
    return () => root.removeEventListener('keydown', handle);
  }, [commands.data, commands.error, commands.loading, profile.error, profile.loading]);
  useEffect(() => {
    const root = host.current?.closest('section[aria-label="工作现场工具"]');
    if (!(root instanceof HTMLElement)) return;
    if (saved?.preferences.reduced_motion === 'reduce') root.dataset.workspaceReducedMotion = 'true';
    else delete root.dataset.workspaceReducedMotion;
    return () => { delete root.dataset.workspaceReducedMotion; };
  }, [saved?.preferences.reduced_motion]);
  return <div ref={host}>
    <details className="experimental-details"><summary>键盘与无障碍偏好</summary>
      <Panel title="当前工作现场的操作偏好">
        <ResourceState loading={profile.loading} error={profile.error} />
        {!!profile.error && <Button onClick={profile.reload}>重新读取操作偏好</Button>}
        {saved?.recovery_required && <StatusMessage tone="warning">偏好记录需要恢复，键盘命令已停用。请显式重置后重新选择。</StatusMessage>}
        {saved && draft && <>
          <Badge>偏好 v{saved.version}</Badge>
          <label className="experimental-check"><input type="checkbox" checked={draft.keyboard_enabled} onChange={event => { touched.current = true; setDraft({ ...draft, keyboard_enabled: event.target.checked }); }} />启用当前工具内的快捷键</label>
          <Field label="命令状态播报"><select value={draft.announcements} onChange={event => { touched.current = true; setDraft({ ...draft, announcements: event.target.value as 'polite' | 'off' }); }}><option value="polite">礼貌播报</option><option value="off">关闭普通命令播报</option></select></Field>
          <Field label="工作现场动态效果"><select value={draft.reduced_motion} onChange={event => { touched.current = true; setDraft({ ...draft, reduced_motion: event.target.value as 'system' | 'reduce' }); }}><option value="system">跟随系统</option><option value="reduce">减少动态效果</option></select></Field>
          <p>快捷键只在当前工作现场内生效，输入框、正文、输入法组词和重复按键不触发。未保存的输入仍会要求确认。</p>
          <div className="experimental-actions">
            <Button disabled={action.busy || profile.loading || !!profile.error || saved.recovery_required || !hasDraft} onClick={() => action.run(async () => publish(await api.save(saved.version, draft)), '操作偏好已保存')}>保存操作偏好</Button>
            <Button disabled={action.busy || !hasDraft} onClick={() => { epoch.current++; touched.current = false; setDraft(saved.preferences); setPending(undefined); }}>取消偏好修改</Button>
            <Button disabled={action.busy || profile.loading || !!profile.error} onClick={() => action.run(async () => publish(await api.reset(saved.version)), '操作偏好已重置')}>重置操作偏好</Button>
          </div>
          {action.feedback}
          <ResourceState loading={commands.loading} error={commands.error} />
          {!commands.error && commands.data?.items.map(command => <div className="experimental-actions" key={command.id}><Button disabled={commands.loading || action.busy || saved.recovery_required} onClick={() => void enter(command)}>{command.label}命令</Button><span>{command.shortcut || '快捷键未启用'}</span></div>)}
          <details><summary>操作偏好历史</summary><ResourceState loading={history.loading} error={history.error} empty={!history.data?.items.length} />{history.data?.items.map(row => <div className="experimental-actions" key={row.version}><span>v{row.version} · {row.state}</span><Button disabled={action.busy || row.state !== 'READY' || !!profile.error || profile.loading} onClick={() => action.run(async () => publish(await api.restore(saved.version, row.version)), '已创建新的恢复版本')}>恢复偏好 v{row.version}</Button></div>)}</details>
        </>}
      </Panel>
    </details>
    {pending && <Panel title="切换工作现场前确认" aria-label="切换工作现场前确认"><p>当前有未保存输入。切换会保留当前工作现场草稿；不会替你保存或发送。</p><div className="experimental-actions"><Button onClick={() => void enter(pending, true)}>继续切换到{pending.label}</Button><Button onClick={() => { epoch.current++; setPending(undefined); }}>留在当前工具</Button></div></Panel>}
    {notice && <p role={saved?.preferences.announcements === 'off' ? undefined : 'status'} aria-live={saved?.preferences.announcements || 'polite'}>{notice}</p>}
  </div>;
}
