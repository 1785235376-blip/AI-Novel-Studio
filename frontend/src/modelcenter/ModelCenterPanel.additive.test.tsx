// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { ModelCenterPanel } from './ModelCenterPanel';
import { type ModelCenterPanelProps } from './modelCenterTypes';

const project = 'model-center-project';
const storageUrl = `/api/projects/${project}/studio/storage`;

const model = (overrides: Record<string, unknown> = {}) => ({
  id: 'llama-cpp-qwen', display_name: 'Qwen 本地', family: 'QWEN', variant: '7B', version: '1',
  capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF',
  status: 'READY', verified: true, metadata: { sha256: 'a'.repeat(64), installed: true },
  hardware_profile_details: [{ id: 'p1', model_id: 'llama-cpp-qwen', gpu_name: 'RTX', profile_kind: 'SMOKE', vram_required: 8192, ram_required: 16384, tested: false }],
  ...overrides,
});

const runtimes = (instance: Record<string, unknown> = {}) => ({
  items: [{
    id: 'llama-cpp-local', runtime_type: 'LLAMA_CPP', status: 'CONFIGURED', management: 'MANAGED',
    capabilities: ['TEXT'], base_url: 'http://127.0.0.1:8081',
    instance: { state: 'RUNNING', process_alive: true, http_reachable: true, loaded_models: ['llama-cpp-qwen'], ...instance },
    discovery: { path_exists: true, executable_exists: true },
  }],
});

const storage = (overrides: Record<string, unknown> = {}) => ({
  assets: { count: 3, bytes: 900 }, trash: { count: 2, bytes: 100 },
  limits: { asset_bytes: 25 * 1024 * 1024, project_asset_bytes: 512 * 1024 * 1024, project_assets: 1000 },
  model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER',
  export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false,
  admission: {
    state: 'READY', available_import_bytes: 1024, reserve_bytes: 64 * 1024 * 1024,
    measurement: 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA',
    paths: { project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD' },
    external_model_scan: false, automatic_cleanup: false, automatic_migration: false,
  },
  ...overrides,
});

type Route = { models?: unknown; runtimes?: unknown; capabilities?: unknown; storage?: unknown };

function mount(route: Route, overrides: Partial<ModelCenterPanelProps> = {}) {
  const calls: string[] = [];
  const transport: StudioGraphTransport = {
    json: async <T,>(url: string): Promise<T> => {
      calls.push(url);
      if (url === '/api/model-center/models') {
        if (route.models instanceof Error) throw route.models;
        return (route.models ?? { items: [model()] }) as T;
      }
      if (url === '/api/model-center/runtimes') {
        if (route.runtimes instanceof Error) throw route.runtimes;
        return (route.runtimes ?? runtimes()) as T;
      }
      if (url.endsWith('/capabilities')) {
        if (route.capabilities instanceof Error) throw route.capabilities;
        return (route.capabilities ?? { runtime_id: 'llama-cpp-local', detected_at: '2026-10-14T09:00:00Z', runtime_state: 'RUNNING', capabilities: ['TEXT'] }) as T;
      }
      if (url === storageUrl) {
        if (route.storage instanceof Error) throw route.storage;
        return (route.storage ?? storage()) as T;
      }
      throw new Error(`unexpected request: ${url}`);
    },
  };
  const props: ModelCenterPanelProps = {
    projectId: project, transport, identity: 'identity-1', active: true, denied: false, busy: false,
    isCurrent: () => true, read: work => work(), mutate: work => work(), ...overrides,
  };
  const view = render(<ModelCenterPanel {...props} />);
  return { ...view, calls, props, transport };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const surface = () => document.querySelector('.model-center-panel') as HTMLElement | null;
const surfaceState = () => surface()?.dataset.surfaceState;
const sourceState = (source: 'catalog' | 'storage') => surface()?.dataset[source === 'catalog' ? 'catalogState' : 'storageState'];

describe('ModelCenterPanel partial reads and recovery', () => {
  it('reports a failed catalog alongside successful storage, then recovers on explicit retry', async () => {
    const route: Route = { models: new Error('temporary read failure') };
    const { calls } = mount(route);
    await waitFor(() => expect(sourceState('catalog')).toBe('FAILED'));
    expect(surfaceState()).toBe('PARTIAL');
    expect(screen.queryByText('注册表为空')).toBeNull();
    expect(screen.queryByText('没有注册模型')).toBeNull();
    expect(screen.getByText(/模型注册表或运行时读取失败/)).toBeTruthy();
    expect(screen.getByLabelText('用量与配额').textContent).toContain('1,000 字节');
    const retry = screen.getByRole('button', { name: '重新读取模型注册表' }) as HTMLButtonElement;
    expect(retry.disabled).toBe(false);
    const before = calls.length;
    route.models = { items: [model()] };
    fireEvent.click(retry);
    await waitFor(() => expect(surfaceState()).toBe('READY'));
    expect(calls).toHaveLength(before + 4);
    expect(screen.queryByText(/模型注册表或运行时读取失败/)).toBeNull();
    expect(screen.getByLabelText('模型详情')).toBeTruthy();
  });

  it('never calls unavailable sources an empty registry', async () => {
    const unavailable = new ApiError({ status: 404, code: 'SOURCE_UNAVAILABLE', message: 'unavailable' });
    mount({ models: unavailable, storage: unavailable });
    await waitFor(() => expect(sourceState('catalog')).toBe('UNAVAILABLE'));
    expect(surfaceState()).toBe('FAILED');
    expect(screen.queryByText('注册表为空')).toBeNull();
    expect(screen.getByText(/模型注册表或运行时暂不可读取/)).toBeTruthy();
  });

  it('does not claim a complete empty read when the runtime read failed', async () => {
    mount({ models: { items: [] }, runtimes: new Error('runtime read failed') });
    await waitFor(() => expect(sourceState('catalog')).toBe('FAILED'));
    expect(surfaceState()).toBe('PARTIAL');
    expect(screen.queryByText('注册表为空')).toBeNull();
    expect(screen.queryByText('没有注册模型')).toBeNull();
    expect(screen.getByText(/模型注册表或运行时读取失败/)).toBeTruthy();
  });

  it('labels retained catalog and storage values after a refresh failure', async () => {
    const route: Route = {};
    mount(route);
    await waitFor(() => expect(surfaceState()).toBe('READY'));
    route.models = new Error('catalog refresh failed');
    route.storage = new Error('storage refresh failed');
    fireEvent.click(screen.getByRole('button', { name: '重新读取模型注册表' }));
    await waitFor(() => expect(surfaceState()).toBe('FAILED'));
    expect(screen.getByText(/模型注册表或运行时读取失败/)).toBeTruthy();
    expect(screen.getByText(/保留已读取的模型事实/)).toBeTruthy();
    expect(screen.getByText(/保留上一次成功读取的存储事实/)).toBeTruthy();
    expect(screen.getByLabelText('模型详情')).toBeTruthy();
    expect(screen.getByLabelText('用量与配额').textContent).toContain('1,000 字节');
  });

  it('announces loading without premature unavailable or failure messages', async () => {
    let complete!: () => void;
    const pending = new Promise<void>(resolve => { complete = resolve; });
    mount({}, { read: async work => { await pending; return work(); } });
    await waitFor(() => expect(surfaceState()).toBe('LOADING'));
    expect(surface()?.getAttribute('aria-busy')).toBe('true');
    expect(screen.queryByText(/当前服务未提供项目存储读取/)).toBeNull();
    expect(screen.queryByText(/没有读取到项目存储投影：/)).toBeNull();
    expect((screen.getByRole('button', { name: '重新读取模型注册表' }) as HTMLButtonElement).disabled).toBe(true);
    complete();
    await waitFor(() => expect(surfaceState()).toBe('READY'));
    expect(surface()?.getAttribute('aria-busy')).toBe('false');
  });
});

describe('ModelCenterPanel retained facts review regressions', () => {
  it('labels storage retained after an unavailable refresh and distinguishes current usage from old values', async () => {
    const route: Route = {};
    mount(route);
    await waitFor(() => expect(surfaceState()).toBe('READY'));
    route.storage = new ApiError({ status: 404, code: 'SOURCE_UNAVAILABLE', message: 'unavailable' });
    fireEvent.click(screen.getByRole('button', { name: '重新读取存储事实' }));
    await waitFor(() => expect(sourceState('storage')).toBe('UNAVAILABLE'));
    expect(screen.getByLabelText('用量与配额').textContent).toContain('1,000 字节');
    expect(screen.getByText(/保留上一次成功读取的存储事实/)).toBeTruthy();
    expect(screen.getByText(/当前用量未知，所列旧值仅供对照/)).toBeTruthy();
  });

  it('does not offer unavailable-catalog recovery advice when the panel is explicitly denied', () => {
    const { calls } = mount({}, { denied: true });
    expect(calls).toEqual([]);
    expect(screen.queryByText(/模型注册表或运行时暂不可读取/)).toBeNull();
  });
});
