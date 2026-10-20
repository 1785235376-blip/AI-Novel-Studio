import { healthParts, permissionIds, permissionLabels, type DesktopSnapshot, type DesktopState } from '../../src/interop/desktop';

/** Synthetic UI/API projection only: never evidence of native desktop trust. */
export function desktopFixture(state: DesktopState = 'UNTRUSTED', sessionId = 'session'): DesktopSnapshot {
  return {
    state, transport_state: 'READY', boundary: 'LOCAL_REQUIRED',
    connections: [{ session_id: sessionId, product_display_name: 'Synthetic Tutor', product_id: 'poemseed.tutor.desktop', product_version: '0.1.0', protocol_version: '1.0',
      trust_level: 'UNVERIFIED', transport: 'LOOPBACK_HTTP', mode: 'MOCK_ONLY', transport_connected: true, handshake_complete: true,
      peer_authenticated: false, session_established: true, capabilities_negotiated: true,
      capabilities: ['project.context.read', 'project.selection.share', 'tutor.guidance.request', 'diagnostics.read'], session_age_seconds: 12, expires_at: '2099-01-01T00:00:00Z',
      permissions: permissionIds.map(id => ({ id, label: permissionLabels[id], capabilities: [], state: 'AVAILABLE', standing: id === 'standing_metadata_events' })), standing_permissions: [] }],
    health: Object.fromEntries(healthParts.map(id => [id, id === 'peer' ? 'DEGRADED' : 'READY'])) as DesktopSnapshot['health'],
    event_sources: [{ module: 'CHAPTER', provenance: 'DIRECT_EVENT' }, { module: 'MODEL', provenance: 'POLLING' }, { module: 'TUTOR', provenance: 'SYNTHETIC' }],
    diagnostics: { protocol_version: '1.0', error_codes: [], trust_state: 'UNVERIFIED', state_machine: 'READY', timings: {} },
  };
}
