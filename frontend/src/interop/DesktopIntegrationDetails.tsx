import { Badge, Button, Panel } from '../ui/primitives';
import { currentDesktopConnection, desktopPermission, desktopState, desktopStateLabels, healthParts, healthState, permissionIds, permissionLabels, type DesktopSnapshot, type PermissionId } from './desktop';

export function DesktopStateBadge({ snapshot, pending }: { snapshot?: DesktopSnapshot; pending?: boolean }) {
  const state = pending ? 'UNKNOWN' : desktopState(snapshot?.state);
  return <span aria-label="桌面集成状态" aria-live="polite"><Badge tone={state === 'DEGRADED' || state === 'UNTRUSTED' ? 'warning' : state === 'AUTHORIZED' || state === 'CONNECTED' ? 'info' : 'neutral'}>{desktopStateLabels[state]}</Badge></span>;
}

export function DesktopIntegrationDetails({ snapshot, sessionId, busy, pending, onRefresh, onRevoke }: {
  snapshot?: DesktopSnapshot; sessionId?: string; busy: boolean; pending: boolean; onRefresh: () => void; onRevoke: (id: PermissionId) => void;
}) {
  const connection = currentDesktopConnection(snapshot, sessionId);
  const permissionState = (id: PermissionId) => pending ? 'UNKNOWN' : desktopPermission(connection, id)?.state ?? 'UNKNOWN';
  const stageLabel = (value: boolean | undefined) => pending || value === undefined ? 'UNKNOWN' : value ? '已确认' : '未确认';
  const expires = connection?.expires_at && Number.isFinite(Date.parse(connection.expires_at)) ? connection.expires_at : 'UNKNOWN';
  return <>
    <Panel title="Connection Detail · 连接详情" actions={<Button disabled={busy} onClick={onRefresh}>刷新主机状态</Button>} aria-label="连接详情">
      <p>连接成功 ≠ 已经授权正文。Product ID 是对方声明的信息，不能代替身份认证。参考连接的真实 Desktop 接入仍为 LOCAL_REQUIRED。</p>
      <dl className="local-tutor-facts">
        <div><dt>Product display name</dt><dd>{connection ? `${connection.product_display_name} · ${connection.mode}` : '未连接'}</dd></div>
        <div><dt>Stable Product ID</dt><dd>{connection?.product_id ?? 'UNKNOWN'}</dd></div>
        <div><dt>Product version</dt><dd>{connection?.product_version ?? 'UNKNOWN'}</dd></div>
        <div><dt>Protocol version</dt><dd>{connection?.protocol_version ?? snapshot?.diagnostics?.protocol_version ?? 'UNKNOWN'}</dd></div>
        <div><dt>Trust level</dt><dd>{connection?.trust_level ?? 'UNKNOWN'}{connection?.mode === 'MOCK_ONLY' ? ' · MOCK_ONLY 不代表生产信任' : ''}</dd></div>
        <div><dt>Transport</dt><dd>{connection?.transport ?? 'UNKNOWN'} · {snapshot?.transport_state ?? 'UNKNOWN'}</dd></div>
        <div><dt>Session age</dt><dd>{!pending && Number.isFinite(connection?.session_age_seconds) ? `${Math.max(0, Math.floor(connection!.session_age_seconds))} 秒（主机快照）` : 'UNKNOWN'}</dd></div>
        <div><dt>Expiry</dt><dd>{expires}</dd></div>
        <div><dt>Standing permissions</dt><dd>{pending ? 'UNKNOWN' : connection ? connection.standing_permissions?.map(id => permissionLabels[id] ?? 'UNKNOWN').join('、') || '无持续授权' : 'UNKNOWN'}</dd></div>
      </dl>
      <ol className="local-tutor-stages" aria-label="连接阶段">
        <li>Transport Connected：{stageLabel(connection?.transport_connected)}</li>
        <li>Protocol Handshake Complete：{stageLabel(connection?.handshake_complete)}</li>
        <li>Peer Authenticated：{stageLabel(connection?.peer_authenticated)}</li>
        <li>Session Established：{stageLabel(connection?.session_established)}</li>
        <li>Capabilities Negotiated：{stageLabel(connection?.capabilities_negotiated)}</li>
      </ol>
      {!pending && connection?.standing_metadata_fields?.length ? <p>已确认的持续元数据类别：{connection.standing_metadata_fields.join(' · ')}</p> : null}
      <p>Capabilities（协商能力不等于内容授权）：{connection?.capabilities?.join(' · ') || '尚未协商'}</p>
    </Panel>
    <Panel title="Permission Center · 权限中心" aria-label="权限中心">
      <p>AVAILABLE 表示可请求此能力，仍需单次预览和确认；GRANTED 只表示主机确认的授权范围。撤销会使关联预览与后续请求失效。已发送的信息无法撤回。</p>
      <ul className="local-tutor-permissions">
        {permissionIds.map(id => <li key={id} aria-label={permissionLabels[id]}>
          <div><strong>{permissionLabels[id]}</strong><p>{['selection', 'current_chapter', 'specific_context'].includes(id) ? '正文每次单独确认，不建立持续正文授权。' : id === 'standing_metadata_events' ? '仅本次会话明确确认的元数据事件；重连不恢复。' : id === 'deep_link' ? '每次必须由用户点击，指导不会自动执行。' : '仅本次明确选择的元数据范围。'}</p></div>
          <Badge tone={permissionState(id) === 'GRANTED' ? 'info' : 'neutral'}>{permissionState(id)}</Badge>
          <Button disabled={busy || !sessionId || pending || !['AVAILABLE', 'GRANTED'].includes(permissionState(id))} onClick={() => onRevoke(id)} aria-label={`撤销 ${permissionLabels[id]}`}>撤销</Button>
        </li>)}
      </ul>
      <p>独立撤销不会删除 Studio 作品、Tutor Memory 或 Case DB。重新连接不恢复旧 Session、正文确认或持续事件授权。</p>
    </Panel>
    <Panel title="Interop Health · 集成健康" aria-label="集成健康">
      <p>Tutor 或验证器不可用时，Studio 主程序仍可继续使用。</p>
      <dl className="local-tutor-facts">{healthParts.map(part => <div key={part}><dt>{part}</dt><dd><Badge tone={!pending && healthState(snapshot?.health?.[part]) === 'DEGRADED' ? 'warning' : 'neutral'}>{pending ? 'UNKNOWN' : healthState(snapshot?.health?.[part])}</Badge></dd></div>)}</dl>
      <p>Event source evidence：</p>
      {snapshot?.event_sources?.length ? <ul>{snapshot.event_sources.map(source => <li key={source.module}>{source.module} · {source.provenance}</li>)}</ul> : <p>UNKNOWN · 尚无来源证据</p>}
      <p>DIRECT_EVENT：业务直接事件；POLLING：轮询；SYNTHETIC：合成夹具。不会把轮询显示为实时。</p>
      <p>Desktop / Named Pipe / signed binary / real install registry：LOCAL_REQUIRED。</p>
    </Panel>
  </>;
}
