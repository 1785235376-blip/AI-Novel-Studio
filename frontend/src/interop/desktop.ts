// Product-host projection only. These types are not PoemSeed 1.0 wire additions.
export const desktopStates = ['NOT_INSTALLED', 'DETECTED', 'UNTRUSTED', 'READY', 'CONNECTED', 'AUTHORIZED', 'DEGRADED', 'DISCONNECTED', 'UNKNOWN'] as const;
export type DesktopState = typeof desktopStates[number];
export const permissionIds = ['app_status', 'task_status', 'model_metadata', 'diagnostics', 'selection', 'current_chapter', 'specific_context', 'standing_metadata_events', 'deep_link'] as const;
export type PermissionId = typeof permissionIds[number];
export const healthParts = ['transport', 'peer', 'session', 'capabilities', 'events', 'tutor', 'verifier'] as const;
export type HealthState = 'READY' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN';
export type DesktopPermission = { id: PermissionId; label: string; capabilities: string[]; state: 'AVAILABLE' | 'REVOKED' | 'GRANTED'; standing: boolean };
export type DesktopConnection = {
  session_id: string; product_display_name: string; product_id: string; product_version: string; protocol_version: string;
  trust_level: string; transport: string; mode: 'MOCK_ONLY' | 'LOCAL_REFERENCE';
  transport_connected: boolean; handshake_complete: boolean; peer_authenticated: boolean; session_established: boolean; capabilities_negotiated: boolean;
  capabilities: string[]; session_age_seconds: number; expires_at: string;
  permissions: DesktopPermission[]; standing_permissions: PermissionId[]; standing_metadata_fields?: string[];
};
export type DesktopSnapshot = {
  state: DesktopState; transport_state: string; boundary: 'LOCAL_REQUIRED'; connections: DesktopConnection[];
  health: Record<typeof healthParts[number], HealthState>;
  event_sources: { module: string; provenance: 'DIRECT_EVENT' | 'POLLING' | 'SYNTHETIC' }[];
  diagnostics: { protocol_version: string; error_codes: string[]; trust_state: string; state_machine: string; timings: Record<string, number> };
};
export type PermissionRevokeReceipt = { request_id: string; session_id: string; permission_id: PermissionId; status: 'REVOKED'; permissions: DesktopPermission[]; desktop: DesktopSnapshot };
export type EmergencyReceipt = {
  request_id: string; session_id: string; status: 'DISCONNECTED' | 'UNKNOWN'; revoked: boolean;
  subscriptions_stopped: boolean; pending_cancelled: boolean; standing_grants_cleared: boolean; transport_disconnected: boolean;
  transport_close_state?: 'CLOSED' | 'UNKNOWN' | 'TIMEOUT' | 'FAILED'; peer_disconnect_acknowledged?: boolean;
};
export const permissionLabels: Record<PermissionId, string> = {
  app_status: 'App Status · 软件状态', task_status: 'Task Status · 任务状态', model_metadata: 'Model Metadata · 模型元数据', diagnostics: 'Diagnostics · 诊断',
  selection: 'Selection · 选中文本', current_chapter: 'Current Chapter · 当前章节', specific_context: 'Specific Context · 指定资料',
  standing_metadata_events: 'Standing Metadata Events · 持续元数据事件', deep_link: 'Deep Link · 用户点击导航',
};
export const desktopStateLabels: Record<DesktopState, string> = {
  NOT_INSTALLED: 'Not Installed · 未安装', DETECTED: 'Detected · 已发现', UNTRUSTED: 'Untrusted · 未信任', READY: 'Ready · 已准备',
  CONNECTED: 'Connected · 已连接', AUTHORIZED: 'Authorized · 已授权', DEGRADED: 'Degraded · 部分不可用', DISCONNECTED: 'Disconnected · 已断开', UNKNOWN: 'Unknown · 状态未知',
};

/** Missing, old-host or invalid state is Unknown, never inferred from an error string. */
export function desktopState(value: unknown): DesktopState {
  return desktopStates.includes(value as DesktopState) ? value as DesktopState : 'UNKNOWN';
}
export function healthState(value: unknown): HealthState {
  return ['READY', 'DEGRADED', 'UNAVAILABLE', 'UNKNOWN'].includes(value as string) ? value as HealthState : 'UNKNOWN';
}
export function currentDesktopConnection(snapshot: DesktopSnapshot | undefined, sessionId: string | undefined): DesktopConnection | undefined {
  if (!sessionId || !Array.isArray(snapshot?.connections)) return undefined;
  const matches = snapshot.connections.filter(value => value?.session_id === sessionId);
  // Ambiguous/duplicate session rows are not authority.
  return matches.length === 1 ? matches[0] : undefined;
}
export function desktopPermission(connection: DesktopConnection | undefined, id: PermissionId) {
  if (!Array.isArray(connection?.permissions)) return undefined;
  const matches = connection.permissions.filter(value => value?.id === id);
  return matches.length === 1 && ['AVAILABLE', 'REVOKED', 'GRANTED'].includes(matches[0].state) ? matches[0] : undefined;
}
