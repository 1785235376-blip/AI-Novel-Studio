// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DirectorModelControls } from './DirectorModelControls';
import { creativeClient, type DirectorProposal, type DirectorModelRoute } from './client';

const proposal: DirectorProposal = { id: 'proposal-1', version: 2, status: 'NEEDS_REVIEW', source_document_id: 'source-1', source_version: 4, title: 'Local suggestion', director_notes: [], output_digest: 'output-digest', provenance: { model_called: false } };
const routes: DirectorModelRoute[] = [{ route_id: 'route-1', provider_id: 'local', model_id: 'director-1', available: true, synthetic: false, reasons: [] }, { route_id: 'route-2', provider_id: 'local', model_id: 'director-2', available: true, synthetic: false, reasons: [] }];
function setup(initial = proposal, routeRows = routes) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const body = url.endsWith('/model-routes') ? { items: routeRows } : url.endsWith('/preview') ? { ...proposal, version: 3, model_preview: { preview_digest: 'preview-reviewed', execution_available: true, model_called: false, allow_cloud_fallback: false, automatic_retry: false, timeout_seconds: 30, source_strategy: 'SAVED_SCREENPLAY', request: { scenes: [{ action: 'Saved input' }] }, broker: { chosen: { provider_id: 'local', model_id: 'director-1', price: { reserve_microusd: 0 } } } } } : { ...proposal, version: 4, status: 'MODEL_RUNNING', model_execution: { job_id: 'job-1', status: 'RUNNING', model_called: false, receipt_state: 'PENDING', usage_state: 'PENDING' } };
    return { ok: true, status: 200, json: async () => body };
  });
  vi.stubGlobal('fetch', fetchMock); const onDenied = vi.fn(); const client = creativeClient('n', { sessionToken: 'session' });
  function Harness() { const [current, setCurrent] = useState(initial); return <DirectorModelControls client={client} proposal={current} disabled={false} run={async action => { await action(); }} onUpdate={setCurrent} />; }
  render(<Harness />); return { fetchMock, onDenied, mutations: () => fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET') };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('optional model calls are explicit and preview-bound', () => {
  it('does not invoke a model when routes load or preview is read', async () => {
    const { mutations } = setup(); await waitFor(() => expect(screen.queryByText('读取本地模型路由…')).toBeNull()); expect(mutations()).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: '预览模型输入' })); await screen.findByText('预览尚未调用模型');
    const dispatch = screen.getByRole('button', { name: '确认调用本地模型' }) as HTMLButtonElement;
    expect(dispatch.disabled).toBe(true); fireEvent.click(dispatch); expect(mutations()).toHaveLength(1); expect(mutations()[0][0]).toContain('/preview');
    expect(screen.getByText(/最高费用：0 USD/)).toBeTruthy(); expect(screen.getByText(/不自动重试或转云端/)).toBeTruthy();
  });

  it('dispatches once with the reviewed preview digest and resets approval on route change', async () => {
    const { mutations } = setup(); await waitFor(() => expect(screen.queryByText('读取本地模型路由…')).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: '预览模型输入' })); await screen.findByText('预览尚未调用模型');
    const check = screen.getByLabelText('已核对输入和本地路由，允许调用一次') as HTMLInputElement;
    fireEvent.click(check); expect(check.checked).toBe(true); fireEvent.change(screen.getByLabelText('本地导演模型'), { target: { value: 'route-2' } });
    expect(check.checked).toBe(false); expect((screen.getByRole('button', { name: '确认调用本地模型' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('本地导演模型'), { target: { value: 'route-1' } }); fireEvent.click(check); fireEvent.click(screen.getByRole('button', { name: '确认调用本地模型' }));
    await screen.findByText('任务：job-1'); expect(mutations()).toHaveLength(2); expect(mutations()[1][0]).toContain('/dispatch');
    expect(JSON.parse(String(mutations()[1][1].body))).toEqual({ expected_version: 3, reviewed_preview_digest: 'preview-reviewed' });
    expect(screen.queryByRole('button', { name: '确认调用本地模型' })).toBeNull();
  });

  it('fails closed for unavailable or synthetic routes', async () => {
    const { mutations } = setup(proposal, [{ ...routes[0], available: false, reasons: ['PRICE_UNKNOWN'] }, { ...routes[1], synthetic: true }]);
    await screen.findByText(/尚无可用的本地模型路由/); expect((screen.getByRole('button', { name: '预览模型输入' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('option', { name: /director-2/ })).toBeNull(); fireEvent.click(screen.getByRole('button', { name: '预览模型输入' })); expect(mutations()).toHaveLength(0);
  });
});
