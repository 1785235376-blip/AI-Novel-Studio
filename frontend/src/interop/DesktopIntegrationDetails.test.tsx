// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { desktopFixture } from '../../tests/fixtures/desktopInterop';
import { DesktopIntegrationDetails, DesktopStateBadge } from './DesktopIntegrationDetails';
import { currentDesktopConnection, desktopPermission, desktopStates, desktopStateLabels, healthParts, permissionIds, permissionLabels } from './desktop';
afterEach(cleanup);

it.each(desktopStates)('renders the formal %s host state without interpreting transport errors', state => {
  render(<DesktopStateBadge snapshot={desktopFixture(state)} />);
  expect(screen.getByLabelText('桌面集成状态').textContent).toBe(desktopStateLabels[state]);
});
it.each([undefined, 'TRANSPORT_ERROR', 'Connected', 'READY / success'])('unknown state %s stays Unknown', state => {
  render(<DesktopStateBadge snapshot={{ ...desktopFixture(), state } as any} />);
  expect(screen.getByLabelText('桌面集成状态').textContent).toBe(desktopStateLabels.UNKNOWN);
});
it('shows Unknown while a mutation receipt or refreshed state is pending', () => {
  render(<DesktopStateBadge snapshot={desktopFixture('AUTHORIZED')} pending />);
  expect(screen.getByLabelText('桌面集成状态').textContent).toBe(desktopStateLabels.UNKNOWN);
});
it('shows scoped details, five independent phases, exact evidence provenance and seven health parts', () => {
  render(<DesktopIntegrationDetails snapshot={desktopFixture()} sessionId="session" busy={false} pending={false} onRefresh={vi.fn()} onRevoke={vi.fn()} />);
  const details = screen.getByLabelText('连接详情');
  for (const value of ['Synthetic Tutor · MOCK_ONLY', 'poemseed.tutor.desktop', '0.1.0', '1.0', 'UNVERIFIED', 'LOOPBACK_HTTP', '12 秒（主机快照）', '2099-01-01T00:00:00Z']) expect(details.textContent).toContain(value);
  expect(details.textContent).toContain('连接成功 ≠ 已经授权正文');
  expect(within(screen.getByLabelText('连接阶段')).getAllByRole('listitem')).toHaveLength(5);
  expect(screen.getByText('Peer Authenticated：未确认')).toBeTruthy();
  const health = screen.getByLabelText('集成健康');
  for (const part of healthParts) expect(within(health).getByText(part)).toBeTruthy();
  for (const source of ['CHAPTER · DIRECT_EVENT', 'MODEL · POLLING', 'TUTOR · SYNTHETIC']) expect(within(health).getByText(source)).toBeTruthy();
});
it('renders all nine independent revoke actions and never describes AVAILABLE as content authorization', () => {
  const revoke = vi.fn(); render(<DesktopIntegrationDetails snapshot={desktopFixture()} sessionId="session" busy={false} pending={false} onRefresh={vi.fn()} onRevoke={revoke} />);
  const center = screen.getByLabelText('权限中心');
  for (const id of permissionIds) { fireEvent.click(within(center).getByRole('button', { name: `撤销 ${permissionLabels[id]}` })); expect(revoke).toHaveBeenLastCalledWith(id); }
  expect(within(center).getAllByText('AVAILABLE')).toHaveLength(9);
  expect(within(center).queryAllByText('GRANTED')).toHaveLength(0);
});
it('cannot use another or a duplicate session row as permission authority', () => {
  const other = desktopFixture('AUTHORIZED', 'other');
  expect(currentDesktopConnection(other, 'session')).toBeUndefined();
  other.connections.push(other.connections[0]); expect(currentDesktopConnection(other, 'other')).toBeUndefined();
  render(<DesktopIntegrationDetails snapshot={other} sessionId="session" busy={false} pending={false} onRefresh={vi.fn()} onRevoke={vi.fn()} />);
  for (const button of within(screen.getByLabelText('权限中心')).getAllByRole('button')) expect((button as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByText('poemseed.tutor.desktop')).toBeNull();
});
it('duplicate or malformed permission states cannot enable revoke controls', () => {
  const data = desktopFixture(); data.connections[0].permissions.push(data.connections[0].permissions[0]);
  expect(desktopPermission(data.connections[0], 'app_status')).toBeUndefined();
  render(<DesktopIntegrationDetails snapshot={data} sessionId="session" busy={false} pending={false} onRefresh={vi.fn()} onRevoke={vi.fn()} />);
  expect((screen.getByRole('button', { name: `撤销 ${permissionLabels.app_status}` }) as HTMLButtonElement).disabled).toBe(true);
});
it('does not present old standing fields as confirmed during an uncertain mutation', () => {
  const data = desktopFixture(); data.connections[0].standing_permissions = ['standing_metadata_events']; data.connections[0].standing_metadata_fields = ['task'];
  data.connections[0].permissions.find(value => value.id === 'standing_metadata_events')!.state = 'GRANTED';
  render(<DesktopIntegrationDetails snapshot={data} sessionId="session" busy={false} pending onRefresh={vi.fn()} onRevoke={vi.fn()} />);
  expect(screen.queryByText(/已确认的持续元数据类别/)).toBeNull();
  expect(within(screen.getByLabelText('权限中心')).queryByText('GRANTED')).toBeNull();
});
