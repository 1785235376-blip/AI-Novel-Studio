import type { ExperimentalClient } from './api';
export type ChecklistItem = { id: string; text: string; done: boolean };
export type Session = { id: string; version: number; status: 'ACTIVE' | 'COMPLETED'; goal: string; target_characters: number | null; tasks: ChecklistItem[]; stopping_note: string; created_at: string; completed_at?: string; recap: { persisted_revision_events: number | null; net_characters: number | null; completed_checklist_items: number; history_available: boolean; statistics_scope: string; attribution: string } | null };
export type NoticePreferences = { version: number; reminder: { enabled: boolean; time: string; timezone: string }; completion_priority: 'normal' | 'low'; review_priority: 'normal' | 'low'; failure_priority: 'urgent' | 'normal' };
export type Notice = { event_id: string; kind: string; priority: string; label: string; status: string; feature: string; task_id: string; authority: string };
export const defaultNoticePreferences: NoticePreferences = { version: 0, reminder: { enabled: false, time: '18:00', timezone: 'UTC' }, completion_priority: 'normal', review_priority: 'normal', failure_priority: 'urgent' };
export function writingSessionsClient(client: ExperimentalClient) {
  const base = '/writing-sessions';
  return {
    overview: (signal?: AbortSignal) => client.get<{ items: Session[]; truncated: boolean; project_goal: { target_words: number; current_words: number; target_chapters: number; current_chapters: number } | null }>(base, signal),
    start: (body: { capture_id: string; goal: string; target_characters: number | null; tasks: ChecklistItem[] }) => client.post<Session>(base, body),
    update: (session: Session, complete: boolean) => client.put<Session>(base + '/' + encodeURIComponent(session.id), { expected_version: session.version, tasks: session.tasks, stopping_note: session.stopping_note, complete }),
    preferences: (signal?: AbortSignal) => client.get<NoticePreferences>(base + '/preferences/notices', signal),
    savePreferences: (settings: NoticePreferences) => client.put<NoticePreferences>(base + '/preferences/notices', { expected_version: settings.version, reminder: settings.reminder, completion_priority: settings.completion_priority, review_priority: settings.review_priority, failure_priority: settings.failure_priority }),
    notices: (focus: boolean, signal?: AbortSignal) => client.get<{ items: Notice[]; deferred_count: number; truncated: boolean; unavailable: unknown[] }>(base + '/notices?focus=' + String(focus), signal),
    acknowledge: (version: number, eventId: string) => client.post<NoticePreferences>(base + '/notices/acknowledge', { expected_version: version, event_id: eventId }),
  };
}
/** Next future wall-clock minute in an IANA zone. DST gaps skip that day;
 * a repeated minute is delivered at most once per mounted timer day. */
export function nextReminderAt(time: string, timezone: string, after: number): number | undefined {
  const fmt = new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  for (let minute = 1; minute <= 60 * 49; minute++) {
    const candidate = Math.floor(after / 60000) * 60000 + minute * 60000;
    if (fmt.format(candidate) === time) return candidate;
  }
  return undefined;
}

const settingsListeners = new WeakMap<ExperimentalClient, Set<() => void>>();
export function watchNoticeSettings(client: ExperimentalClient, listener: () => void) {
  let listeners = settingsListeners.get(client); if (!listeners) { listeners = new Set(); settingsListeners.set(client, listeners); }
  listeners.add(listener); return () => { listeners!.delete(listener); };
}
export function noticeSettingsChanged(client: ExperimentalClient) { settingsListeners.get(client)?.forEach(listener => listener()); }
