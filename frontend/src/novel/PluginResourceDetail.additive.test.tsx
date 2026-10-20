// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api';
import { PluginInspector } from './PluginInspector';
import { resourceBodyText, resourceDetailPin } from './pluginResourceDetailContract';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const inspection = { id: 'continuity-audit-pack', name: '连续性检查包', version: '1.0.0', pluginVersion: '1.0.0',
  status: 'MANIFEST_ACTIVE', publisher: 'PoemSeed', isolation: 'DENY_ALL' };
function fixture(kind = 'workflow_templates', pluginId = inspection.id) {
  const resource = { plugin_id: pluginId, resource_id: 'resources:audit.json', kind, name: '人工检查说明',
    schema_version: '1.0', sha256: 'a'.repeat(64), validated: true, execution_supported: false };
  const catalog = { plugin_id: pluginId, items: [resource], total: 1, resource_count: 1, invalid_resource_count: 0,
    visible: true, validated: true, validation_status: 'VALIDATED', status: 'MANIFEST_ACTIVE',
    execution_supported: false, isolation: 'DENY_ALL', publisher_verified: false };
  const detail = { ...resource, data: { stages: [{ title: 'Human review', intent: 'BODY_CURRENT' }],
    untrusted: '<img src="https://resource.invalid/a.png" onerror="alert(1)"><script>alert(1)</script>',
    reference: 'https://resource.invalid/model', execution_supported: false } };
  return { resource, catalog, detail };
}
const readButton = () => screen.getByRole('button', { name: '读取 人工检查说明 的资源正文' });
const body = () => screen.queryByLabelText('人工检查说明 的资源正文');
async function setup(kind?: string) {
  const f = fixture(kind);
  const summaries = vi.spyOn(api, 'pluginResources').mockResolvedValue(f.catalog);
  const detail = vi.spyOn(api, 'pluginResource').mockResolvedValue(f.detail);
  const rendered = render(<StrictMode><PluginInspector inspection={inspection} /></StrictMode>);
  await screen.findByRole('button', { name: '读取 人工检查说明 的资源正文' });
  return { ...f, receipt: f.detail, summaries, detail, rendered };
}

it.each(['writing_presets', 'workflow_templates', 'export_profiles'])('reads %s only on explicit request, as plain text with no executable or mutation behavior', async kind => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Unexpected URL request'));
  const mutations = ['installPluginPackage', 'registerPlugin', 'enablePlugin', 'setPluginPermissions', 'removePluginPackage'] as const;
  const spies = mutations.map(name => vi.spyOn(api, name));
  const f = await setup(kind);
  expect(f.detail).not.toHaveBeenCalled(); fireEvent.click(readButton());
  await waitFor(() => expect(body()?.textContent).toContain('BODY_CURRENT'));
  expect(f.detail.mock.calls).toEqual([[inspection.id, f.resource.resource_id]]);
  expect(body()?.textContent).toContain('<script>alert(1)</script>');
  expect(body()?.getAttribute('tabindex')).toBe('0');
  expect(document.querySelector('img,script,a[href],iframe')).toBeNull();
  expect(fetch).not.toHaveBeenCalled(); spies.forEach(spy => expect(spy).not.toHaveBeenCalled());
  expect(screen.getByText('PoemSeed（未验证发布者）')).toBeTruthy();
});

it.each([401, 403, 404, 409, 422])('clears an existing body when the original read returns %i, without echoing its error', async status => {
  const f = await setup(); fireEvent.click(readButton());
  await waitFor(() => expect(body()).not.toBeNull());
  f.detail.mockRejectedValue(new ApiError({ status, code: 'PLUGIN_MANIFEST_DRIFT', message: 'PRIVATE_ERROR_PATH' }));
  fireEvent.click(readButton()); expect(body()).toBeNull(); await screen.findByRole('alert');
  expect(screen.queryByText(/PRIVATE_ERROR_PATH/)).toBeNull(); expect(body()).toBeNull();
});

it.each([
  { plugin_id: 'foreign' }, { resource_id: 'resources:foreign.json' }, { kind: 'export_profiles' },
  { sha256: 'b'.repeat(64) }, { schema_version: '2.0' }, { validated: false }, { execution_supported: true },
  { error_code: 'PLUGIN_ID_DUPLICATE' }, { validation_status: 'DRIFT' }, { status: 'DISABLED' },
])('rejects a mismatched or denied full-body receipt: %j', patch => {
  const f = fixture(), pin = resourceDetailPin(inspection.id, f.catalog, f.resource)!;
  expect(pin).toBeTruthy(); expect(() => resourceBodyText({ ...f.detail, ...patch }, pin)).toThrow();
});

it.each(['DISABLED', 'DRIFT', 'DUPLICATE', 'PARTIAL', 'REVIEW_REQUIRED', 'duplicate-resource'])('does not offer a body from %s catalog state', async state => {
  const f = fixture();
  const catalog = state === 'duplicate-resource'
    ? { ...f.catalog, items: [f.resource, f.resource], total: 2, resource_count: 2 }
    : { ...f.catalog, status: state === 'DISABLED' ? state : f.catalog.status, validation_status: state };
  vi.spyOn(api, 'pluginResources').mockResolvedValue(catalog);
  const detail = vi.spyOn(api, 'pluginResource');
  render(<PluginInspector inspection={inspection} />);
  await waitFor(() => expect(screen.queryByText('正在重新校验声明式资源…')).toBeNull());
  expect(screen.queryByRole('button', { name: /的资源正文/ })).toBeNull(); expect(detail).not.toHaveBeenCalled();
});

it.each(['id', 'version', 'pluginVersion', 'disable', 'refresh'])('discards a pending body after %s change, including return to the same selection', async change => {
  const f = await setup(); let finish!: (value: unknown) => void;
  f.detail.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  fireEvent.click(readButton());
  if (change === 'refresh') fireEvent.click(screen.getByRole('button', { name: '重新校验资源摘要' }));
  else {
    const changed = change === 'id' ? { ...inspection, id: 'genre-fiction-pack' } : change === 'disable'
      ? { ...inspection, status: 'DISABLED' } : { ...inspection, [change]: '2.0.0' };
    f.rendered.rerender(<StrictMode><PluginInspector inspection={changed} /></StrictMode>);
    f.rendered.rerender(<StrictMode><PluginInspector inspection={inspection} /></StrictMode>);
  }
  await screen.findByRole('button', { name: '读取 人工检查说明 的资源正文' });
  await act(async () => finish({ ...f.receipt, data: { secret: 'PRIVATE_LATE_OLD_BODY' } }));
  expect(body()).toBeNull(); expect(screen.queryByText(/PRIVATE_LATE_OLD_BODY/)).toBeNull();
});

it('retires a hidden pending read and accepts only the new request, preventing duplicate clicks', async () => {
  const f = await setup(); let finish!: (value: unknown) => void;
  f.detail.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  fireEvent.click(readButton()); fireEvent.click(readButton()); expect(f.detail).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '收起正文' }));
  fireEvent.click(readButton()); await waitFor(() => expect(body()?.textContent).toContain('BODY_CURRENT'));
  await act(async () => finish({ ...f.receipt, data: { secret: 'PRIVATE_CANCELLED_BODY' } }));
  expect(body()?.textContent).toContain('BODY_CURRENT'); expect(body()?.textContent).not.toContain('PRIVATE_CANCELLED_BODY');
});

it('invalidates the body when refreshing discovers duplicate IDs or manifest drift', async () => {
  const f = await setup(); fireEvent.click(readButton()); await waitFor(() => expect(body()).not.toBeNull());
  f.summaries.mockResolvedValue({ ...f.catalog, validated: false, validation_status: 'DUPLICATE', error_code: 'PLUGIN_ID_DUPLICATE' });
  fireEvent.click(screen.getByRole('button', { name: '重新校验资源摘要' }));
  expect(body()).toBeNull(); await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: /的资源正文/ })).toBeNull();
});

it('does not admit a retained read callback after the plugin is disabled', async () => {
  const f = await setup(), button = readButton();
  const props = (button as any)[Object.keys(button).find(key => key.startsWith('__reactProps$'))!];
  const retained = props.onClick;
  f.rendered.rerender(<PluginInspector inspection={{ ...inspection, status: 'DISABLED' }} />);
  act(() => retained());
  expect(f.detail).not.toHaveBeenCalled(); expect(body()).toBeNull();
});

it('rejects oversized or missing body data rather than returning partial JSON', () => {
  const f = fixture(), pin = resourceDetailPin(inspection.id, f.catalog, f.resource)!;
  expect(() => resourceBodyText({ ...f.detail, data: 'x'.repeat(1024 * 1024) }, pin)).toThrow();
  const { data: _, ...missing } = f.detail;
  expect(() => resourceBodyText(missing, pin)).toThrow();
});
