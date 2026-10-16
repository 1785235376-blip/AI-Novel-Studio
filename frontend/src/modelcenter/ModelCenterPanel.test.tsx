// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { ModelCenterPanel } from './ModelCenterPanel';
import { MODEL_CENTER_CODES, type ModelCenterPanelProps } from './modelCenterTypes';

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

describe('ModelCenterPanel surface states', () => {
  it('renders a denied read as DENIED and never as an empty registry', async () => {
    const onUnavailable = vi.fn();
    mount({
      models: new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied by owner' }),
      storage: new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied by owner' }),
    }, { onUnavailable });
    await waitFor(() => expect(surfaceState()).toBe('DENIED'));
    expect(onUnavailable).toHaveBeenCalled();
    expect((await screen.findAllByText(/读取被拒绝（DENIED）/)).length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain(MODEL_CENTER_CODES.readDenied.message);
    expect(sourceState('catalog')).toBe('DENIED');
    expect(sourceState('storage')).toBe('DENIED');
    expect(screen.queryByText('注册表为空')).toBeNull();
    expect(document.body.textContent).not.toContain('denied by owner');
    // 拒绝之后不得再发出任何读取。
    expect((screen.getByRole('button', { name: '重新读取模型注册表' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '重新读取存储事实' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('keeps EMPTY distinct from a failed read: an empty registry says so explicitly', async () => {
    mount({ models: { items: [] }, runtimes: { items: [] }, storage: storage() });
    await screen.findByText('注册表为空');
    expect(screen.getByText(/空注册表与读取失败是两回事/)).toBeTruthy();
    expect(screen.queryByText(/读取失败（FAILED）/)).toBeNull();
    expect(screen.queryByText(/读取被拒绝（DENIED）/)).toBeNull();
  });

  it('renders an unknown model status as 未提供 instead of guessing a state', async () => {
    mount({ models: { items: [model({ status: undefined, verified: undefined, metadata: undefined })] } });
    const detail = await screen.findByLabelText('模型详情');
    expect(within(detail).getAllByText('未提供').length).toBeGreaterThan(0);
    expect(detail.textContent).toContain('model.status');
    // 结论未知，而不是"可选"。
    expect(within(detail).getByText(/结论未知/)).toBeTruthy();
    expect(within(detail).queryByText(/当前事实允许该模型被路由/)).toBeNull();
  });

  it('states exactly which owner fact blocks a model that cannot route', async () => {
    mount({
      models: { items: [model({ status: 'NOT_INSTALLED' })] },
      runtimes: runtimes({ state: 'STOPPED', http_reachable: false }),
    });
    const blockers = await screen.findByLabelText('阻塞该模型的事实');
    expect(blockers.textContent).toContain('MODEL_STATUS_NOT_READY');
    expect(blockers.textContent).toContain('model.status');
    expect(blockers.textContent).toContain('NOT_INSTALLED');
    expect(blockers.textContent).toContain('RUNTIME_NOT_RUNNING');
    expect(blockers.textContent).toContain('runtime.instance.state');
  });

  it('shows a declared-only capability as 仅声明 and a verified one as 已验证', async () => {
    mount({ models: { items: [model({ verified: false, hardware_profile_details: undefined })] } });
    const matrix = await screen.findByLabelText('能力矩阵：声明与已验证');
    const row = within(matrix).getAllByRole('row')[1];
    expect(within(row).getAllByText('仅声明')).toHaveLength(1);
    expect(within(row).queryByText('已验证')).toBeNull();
    // 每个模态各有一格：文本已声明，其余未声明。
    expect(within(row).getAllByText('未声明')).toHaveLength(3);
  });

  it('marks a capability verified only when the owner record and the runtime observation agree', async () => {
    mount({ models: { items: [model({ verified: true })] } });
    const matrix = await screen.findByLabelText('能力矩阵：声明与已验证');
    const row = within(matrix).getAllByRole('row')[1];
    expect(within(row).getAllByText('已验证')).toHaveLength(1);
  });

  it('keeps every declared capability unverified when no runtime snapshot was read', async () => {
    mount({ capabilities: new ApiError({ status: 404, code: 'MODEL_CENTER_RUNTIME_NOT_FOUND', message: 'no snapshot' }) });
    const matrix = await screen.findByLabelText('能力矩阵：声明与已验证');
    expect(matrix.textContent).toContain('没有读取到任何运行时能力快照');
    expect(within(matrix).queryByText('已验证')).toBeNull();
  });
});

describe('ModelCenterPanel offers no download, cleanup or deletion', () => {
  it('disables every action that would touch models or disk', async () => {
    const { calls } = mount({});
    await screen.findByLabelText('模型详情');
    const download = screen.getByRole('button', { name: /下载模型/ }) as HTMLButtonElement;
    const prepare = screen.getByRole('button', { name: /准备 \/ 修复模型/ }) as HTMLButtonElement;
    const cleanup = screen.getByRole('button', { name: /清理磁盘/ }) as HTMLButtonElement;
    const remove = screen.getByRole('button', { name: /删除孤儿文件/ }) as HTMLButtonElement;
    for (const control of [download, prepare, cleanup, remove]) expect(control.disabled).toBe(true);
    const before = calls.length;
    fireEvent.click(download); fireEvent.click(cleanup); fireEvent.click(remove); fireEvent.click(prepare);
    expect(calls).toHaveLength(before);
  });

  it('issues only GET reads and never a write verb, even after re-reading', async () => {
    const { calls } = mount({});
    await screen.findByLabelText('模型详情');
    const reread = screen.getByRole('button', { name: '重新读取模型注册表' }) as HTMLButtonElement;
    expect(reread.disabled).toBe(false);
    const before = calls.length;
    fireEvent.click(reread);
    // 等到这次刷新真正读完（第二次读取的四个端点都已发出）再检查最后一批请求。
    await waitFor(() => expect(calls.length).toBe(before + 4));
    expect(calls.some(url => /delete|cleanup|download|migrate|start|stop/.test(url))).toBe(false);
    expect(calls.every(url => url.startsWith('/api/model-center/') || url === storageUrl)).toBe(true);
  });

  it('never reads at all while the view is inactive or denied', async () => {
    const inactive = mount({}, { active: false });
    expect(inactive.calls).toEqual([]);
    cleanup();
    const denied = mount({}, { denied: true });
    expect(denied.calls).toEqual([]);
    expect(screen.getByText(/无权查看模型中心/)).toBeTruthy();
  });
});

describe('ModelCenterPanel storage honesty', () => {
  it('reports physical_delete = false and offers no cleanup control', async () => {
    mount({});
    const panel = await screen.findByLabelText('项目存储与冷存储');
    expect(panel.textContent).toContain('physical_delete = false');
    expect(panel.textContent).toContain('MODEL_CENTER_REFERENCES_ONLY');
    expect(panel.textContent).toContain('没有候选');
    expect(within(panel).queryByRole('button', { name: /清理|删除|迁移/ })).toBeNull();
  });

  it('does not render an unmeasured admission as zero', async () => {
    mount({ storage: storage({ admission: { ...(storage().admission as Record<string, unknown>), state: 'UNAVAILABLE', available_import_bytes: null } }) });
    const panel = await screen.findByLabelText('项目存储与冷存储');
    expect(panel.textContent).toContain('未知（不可与 0 互换）');
    expect(panel.textContent).toContain('UNAVAILABLE');
  });

  it('keeps storage facts unknown when the storage read is denied, without claiming there are no assets', async () => {
    mount({ storage: new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied' }) });
    await waitFor(() => expect(sourceState('storage')).toBe('DENIED'));
    const panel = screen.getByLabelText('项目存储与冷存储');
    expect(panel.dataset.storageState).toBe('DENIED');
    expect(panel.textContent).toContain('DENIED');
    expect(panel.textContent).toContain('保持未知');
    expect(panel.textContent).not.toContain('0 项');
    expect(sourceState('catalog')).toBe('READY');
  });
});

describe('ModelCenterPanel provider key state', () => {
  it('shows presence only and never a value', async () => {
    mount({ models: { items: [model({ source: 'CLOUD' })] } });
    const keys = await screen.findByLabelText('Provider 密钥状态（只显示是否存在）');
    expect(keys.textContent).toContain('未知');
    // 说明文字里只有"密钥值不显示"这一条声明，没有任何值形态。
    expect(keys.textContent).toContain('密钥值既不读取、也不渲染');
    expect(keys.textContent).not.toMatch(/sk-|bearer|password/i);
  });

  it('renders PRESENT without ever carrying the secret', async () => {
    const transport: StudioGraphTransport = {
      json: async <T,>(url: string): Promise<T> => {
        if (url === '/api/model-center/models') return { items: [model({ source: 'CLOUD', runtime_type: 'OPENAI_COMPATIBLE_LOCAL' })] } as T;
        if (url === '/api/model-center/runtimes') return { items: [] } as T;
        if (url === storageUrl) return storage() as T;
        if (url.startsWith('/api/credentials/')) return { provider: 'OPENAI_COMPATIBLE_LOCAL', configured: true, backend: 'windows', persistent: true, degraded: false, degraded_reason: null } as T;
        throw new Error(`unexpected ${url}`);
      },
    };
    render(<ModelCenterPanel projectId={project} transport={transport} identity="i" active denied={false} busy={false}
      isCurrent={() => true} read={work => work()} mutate={work => work()} />);
    const keys = await screen.findByLabelText('Provider 密钥状态（只显示是否存在）');
    expect(keys.textContent).toContain('存在');
    expect(keys.textContent).toContain('windows');
    expect(keys.textContent).not.toContain('sk-');
    expect(within(keys).getByText(/密钥值：不显示/)).toBeTruthy();
  });

  it('refuses a credential response that carries a secret key and never renders the value', async () => {
    const transport: StudioGraphTransport = {
      json: async <T,>(url: string): Promise<T> => {
        if (url === '/api/model-center/models') return { items: [model({ source: 'CLOUD', runtime_type: 'OPENAI_COMPATIBLE_LOCAL' })] } as T;
        if (url === '/api/model-center/runtimes') return { items: [] } as T;
        if (url === storageUrl) return storage() as T;
        if (url.startsWith('/api/credentials/')) return { provider: 'OPENAI_COMPATIBLE_LOCAL', configured: true, secret: 'sk-do-not-render' } as T;
        throw new Error(`unexpected ${url}`);
      },
    };
    render(<ModelCenterPanel projectId={project} transport={transport} identity="i" active denied={false} busy={false}
      isCurrent={() => true} read={work => work()} mutate={work => work()} />);
    // 越权回传被整包拒绝：界面只看到"未知"，正文里永远不出现那个值。
    const keys = await screen.findByLabelText('Provider 密钥状态（只显示是否存在）');
    await screen.findByText(/一律显示/);
    expect(document.body.textContent).not.toContain('sk-do-not-render');
    expect(keys.textContent).toContain('未知');
  });
});

describe('ModelCenterPanel scope and injection', () => {
  it('refuses a captured collaboration scope for a different project without reading', async () => {
    const { calls } = mount({}, { scope: { workspaceId: 'w', projectId: 'other', storylineId: 's', branchId: 'b' } });
    await waitFor(() => expect(surfaceState()).toBe('FAILED'));
    expect(calls).toEqual([]);
    expect((await screen.findAllByText(/读取失败（FAILED）/)).length).toBeGreaterThan(0);
    // 范围不一致是契约问题，不是会话被撤销：绝不进入 DENIED。
    expect(surfaceState()).not.toBe('DENIED');
    expect(sourceState('catalog')).toBe('FAILED');
    expect(sourceState('storage')).toBe('FAILED');
  });

  it('accepts injected decoded catalog and storage without re-reading those endpoints', async () => {
    const { calls } = mount({}, {
      catalog: {
        models: [model()], runtimes: [], capability_snapshots: [], hidden_by_authority: 0,
        sources: ['MODEL_CENTER_MODELS', 'MODEL_CENTER_RUNTIMES'],
      },
      storage: {
        assets: { count: 1, bytes: 10 }, trash: { count: 0, bytes: 0 },
        limits: { asset_bytes: 1, project_asset_bytes: 100, project_assets: 10 },
        model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER',
        export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false,
      },
    });
    const detail = await screen.findByLabelText('模型详情');
    expect(detail.textContent).toContain('Qwen 本地');
    const panel = screen.getByLabelText('项目存储与冷存储');
    expect(panel.textContent).toContain('10 字节');
    expect(panel.textContent).toContain('100 字节');
    // 两个来源都已注入：这次不应该再走模型目录或存储端点。
    expect(calls).toEqual([]);
  });

  it('marks injected hardware UNKNOWN when the payload is not an owner fact', async () => {
    mount({}, { hardware: { state: 'MAYBE_FAST' } });
    const detail = await screen.findByLabelText('模型详情');
    expect(detail.textContent).toContain('档位所需字节');
  });

  it('keeps the read-failure code visible and never prints a bare "没有可用模型"', async () => {
    mount({ models: new Error('socket exploded'), storage: new Error('socket exploded') });
    await waitFor(() => expect(surfaceState()).toBe('FAILED'));
    const banners = await screen.findAllByText(/读取失败（FAILED）/);
    expect(banners.some(banner => banner.textContent?.includes(MODEL_CENTER_CODES.readFailed.message))).toBe(true);
    expect(document.body.textContent).not.toContain('socket exploded');
    expect(document.body.textContent).not.toContain('没有可用模型');
    expect(screen.queryByText('注册表为空')).toBeNull();
  });
});

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
