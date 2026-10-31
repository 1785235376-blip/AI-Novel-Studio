// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { AssetBrowserPanel, type AssetBrowserPanelProps } from './AssetBrowserPanel';
import { relationshipGraph, sampleAssets } from './assetBrowserFixtures';
import type { AssetBrowserRelationshipGraph } from './assetBrowserTypes';

const PROJECT = 'novel-ux03';

/** 一份真实的 owner 列表行（`StudioAsset` 投影）。 */
function ownerRow(asset: {
  id: string; filename: string; kind: string; media_type: string; size: number; digest: string;
  created_at: string; updated_at: string | null; version: number;
}): Record<string, unknown> {
  return {
    id: asset.id, novel_id: PROJECT, filename: asset.filename, kind: asset.kind, media_type: asset.media_type,
    size: asset.size, sha256: asset.digest, created_at: asset.created_at, updated_at: asset.updated_at,
    version: asset.version, branch_id: null, deleted_at: null,
    provenance: {
      id: asset.id, label: asset.filename, kind: asset.kind, version: asset.version, digest: asset.digest,
      deleted: false, integrity: 'VERIFIED', origin: 'EXTERNAL_IMPORT',
      license: { label: 'UNSPECIFIED', source: '', note: '' },
      license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', operation: '', parents: [], sources: [],
      stale: false,
    },
    relationships: [], parameters: {},
  };
}
const defaultRows = () => sampleAssets().map(asset => ownerRow({
  id: asset.id, filename: asset.filename, kind: asset.kind, media_type: asset.media_type, size: asset.size,
  digest: asset.digest, created_at: asset.created_at, updated_at: asset.updated_at, version: asset.version ?? 1,
}));

/** 假传输：只回答本目录使用的三个 owner 端点。 */
function fakeTransport(options: {
  items?: Record<string, unknown>[]; graph?: AssetBrowserRelationshipGraph; fail?: 'LIST' | 'DETAIL' | 'GRAPH';
} = {}) {
  const calls: string[] = [];
  const items = options.items ?? defaultRows();
  const graph = options.graph ?? relationshipGraph();
  const transport: StudioGraphTransport = {
    json: <T,>(url: string): Promise<T> => {
      calls.push(url);
      if (url.endsWith('/studio/assets')) {
        return options.fail === 'LIST'
          ? Promise.reject(new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_CHANGED', message: '身份或项目范围已经变化。' }))
          : Promise.resolve({ items } as T);
      }
      if (url.endsWith('/relationships')) {
        return options.fail === 'GRAPH'
          ? Promise.reject(new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_CHANGED', message: '无权读取关系。' }))
          : Promise.resolve(graph as T);
      }
      if (/\/studio\/assets\/[^/]+$/.test(url)) {
        if (options.fail === 'DETAIL') {
          return Promise.reject(new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '详情读取失败。' }));
        }
        const id = url.split('/').pop();
        return Promise.resolve(items.find(row => row.id === id) as T);
      }
      return Promise.resolve({ items } as T);
    },
  };
  return { transport, calls };
}
const panel = (patch: Partial<AssetBrowserPanelProps> = {}, fake = fakeTransport()) => {
  const props: AssetBrowserPanelProps = {
    projectId: PROJECT, transport: fake.transport, identity: 'assetbrowser-view', active: true, denied: false,
    busy: false, isCurrent: () => true, read: work => work(), mutate: work => work(), ...patch,
  };
  return { ...fake, ...render(<AssetBrowserPanel {...props}/>) };
};
/** 只断言这一棵渲染树里的文本（不使用全局 `screen`，避免跨用例残留）。 */
const text = (container: HTMLElement) => container.textContent ?? '';
const inTree = (container: HTMLElement) => within(container);
const click = (container: HTMLElement, name: string | RegExp) =>
  fireEvent.click(inTree(container).getByRole('button', { name }));

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('asset browser view', () => {
  it('renders the owner rows with grid and list sharing one selection', async () => {
    const { container } = panel();
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    expect(container.querySelector('.asset-browser__grid')?.getAttribute('data-mode')).toBe('GRID');

    click(container, '列表');
    expect(container.querySelector('.asset-browser__grid')?.getAttribute('data-mode')).toBe('LIST');
    expect(container.querySelectorAll('.asset-browser__card')).toHaveLength(3);

    click(container, '选择素材 cover.png');
    await waitFor(() => expect(container.querySelectorAll('.asset-browser__card.is-selected')).toHaveLength(1));
    // 切换视图模式不改变选择：网格与列表共用同一个选择模型。
    click(container, '网格');
    expect(container.querySelectorAll('.asset-browser__card.is-selected')).toHaveLength(1);
    expect(text(container)).toContain('cover.png');
  });

  it('renders a denied read as denied, never as an empty library', async () => {
    const fake = fakeTransport({ fail: 'LIST' });
    const { container } = panel({}, fake);
    await waitFor(() => expect(text(container)).toContain('这不是"暂无素材"'));
    expect(text(container)).not.toContain('此项目暂无素材');
    expect(container.querySelector('.asset-browser')?.getAttribute('data-state')).toBe('DENIED');
    expect(fake.calls.some(url => url.endsWith('/studio/assets'))).toBe(true);
  });

  it('shows 未核实 for reference counts until the relationship read succeeds', async () => {
    const fake = fakeTransport();
    const { container } = panel({}, fake);
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    // 列表读取**不**顺带读引用：引用情况是未核实，不是 0。
    expect(text(container)).toContain('引用情况未核实');
    expect(fake.calls.some(url => url.endsWith('/relationships'))).toBe(false);

    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('被哪些镜头 / 节点 / 时间线使用'));
    expect(text(container)).toContain('尚未读取引用关系');
    click(container, /读取引用关系/);
    await waitFor(() => expect(text(container)).toContain('被引用 2 处'));
    expect(fake.calls.some(url => url.endsWith('/relationships'))).toBe(true);
    expect(container.querySelectorAll('.asset-browser__card')).toHaveLength(3);
  });

  it('keeps unverified relationships unverified when the relationship read fails', async () => {
    const { container } = panel({}, fakeTransport({ fail: 'GRAPH' }));
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('尚未读取引用关系'));
    click(container, /读取引用关系/);
    await waitFor(() => expect(text(container)).toContain('引用关系当前不可读'));
    // 未核实 ≠ 未被引用：卡片不会显示"未被引用（已核实）"。
    expect(text(container)).not.toContain('未被引用（已核实）');
    expect(text(container)).toContain('引用');
  });

  it('keeps the current selection and explains why when a detail preview fails', async () => {
    const { container } = panel({}, fakeTransport({ fail: 'DETAIL' }));
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('详情读取失败。'));
    // 选择保持不变：详情面板仍然显示这一行，卡片仍然被选中。
    expect(text(container)).toContain('cover.png');
    expect(container.querySelectorAll('.asset-browser__card.is-selected')).toHaveLength(1);
    expect(text(container)).toContain('详情读取失败 · 选择保持');
    expect(text(container)).toContain('代码 STUDIO_REQUEST_FAILED');
  });

  it('shows the actual available delete impact and never claims a physical delete', async () => {
    const { container } = panel();
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('删除与影响范围'));
    expect(text(container)).toContain('尚未读取引用关系，删除影响范围未知');
    click(container, /读取引用关系/);
    await waitFor(() => expect(text(container)).toContain('被引用 2 处'));
    click(container, '查看可用删除范围');
    await waitFor(() => expect(text(container)).toContain('会影响 2 处引用'));
    expect(text(container)).toContain('物理删除：否');
    expect(text(container)).toContain('不会物理删除你的文件');
    expect(text(container)).toContain('软删除');
  });

  it('sends to another module as a reference only, and never executes it', async () => {
    const onSendTo = vi.fn();
    const fake = fakeTransport();
    const { container } = panel({ onSendTo }, fake);
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('传给其他模块'));

    click(container, '图片模块');
    const before = fake.calls.length;
    click(container, '生成引用（不执行目标模块）');
    expect(onSendTo).toHaveBeenCalledTimes(1);
    const [target, reference] = onSendTo.mock.calls[0];
    expect(target).toBe('IMAGE');
    expect(reference).toEqual({ asset_id: 'asset-a', version: 3, digest: sampleAssets()[0].digest });
    expect(Object.keys(reference).sort()).toEqual(['asset_id', 'digest', 'version']);
    // 只发出引用：没有额外的读取、没有下载、没有写操作。
    expect(fake.calls.length).toBe(before);
    expect(text(container)).toContain('没有复制内容、没有创建第二个原资产、没有执行任何目标模块');
  });

  it('refuses to send a media kind the target module does not accept', async () => {
    const onSendTo = vi.fn();
    const { container } = panel({ onSendTo }, fakeTransport());
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 theme.mp3' })).toBeTruthy());
    click(container, '选择素材 theme.mp3');
    await waitFor(() => expect(text(container)).toContain('传给其他模块'));
    const image = inTree(container).getByRole('button', { name: '图片模块' }) as HTMLButtonElement;
    expect(image.disabled).toBe(true);
    expect(image.title).toContain('只接受');
    expect((inTree(container).getByRole('button', { name: '时间线模块' }) as HTMLButtonElement).disabled).toBe(false);
    expect(onSendTo).not.toHaveBeenCalled();
  });

  it('explains that authorization is not a commercial grant', async () => {
    const { container } = panel();
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('来源与许可'));
    expect(text(container)).toContain('作者许可声明：UNSPECIFIED');
    expect(text(container)).toContain('这是作者声明（AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION）');
    expect(text(container)).toContain('不是法律核验');
    expect(text(container)).toContain('不代表任何云端许可');
    // 从"编辑标签 / 许可"这条路径上永远不可能出现"已商用授权"这种断言。
    expect(text(container)).not.toContain('已获得商用授权');
    expect(text(container)).not.toContain('已授权商用');
  });

  it('never claims a disclosure the owner did not make', async () => {
    const rows = defaultRows().map(row => ({ ...row, provenance: null, tags: ['character'] }));
    const { container } = panel({}, fakeTransport({ items: rows }));
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('来源与许可'));
    expect(text(container)).toContain('原 owner 未披露此素材的来源投影');
    expect(text(container)).not.toContain('这是作者声明');
    // 标签是作者声明，不会改变媒体种类。
    expect(text(container)).toContain('角色');
    expect(text(container)).toContain('图片 · image/png');
  });

  it('keeps a bounded page and never renders the whole library at once', async () => {
    const items = Array.from({ length: 40 }, (_, index) => ownerRow({
      id: `asset-${index}`, filename: `asset-${index}.png`, kind: 'image', media_type: 'image/png', size: 10,
      digest: String(index % 10).repeat(64), created_at: '2026-10-01T00:00:00Z', updated_at: null, version: 1,
    }));
    const { container } = panel({}, fakeTransport({ items }));
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 asset-0.png' })).toBeTruthy());
    expect(container.querySelectorAll('.asset-browser__card')).toHaveLength(24);
    expect(text(container)).toContain('显示 24 / 40 条');
    click(container, '继续显示下一页');
    await waitFor(() => expect(container.querySelectorAll('.asset-browser__card')).toHaveLength(40));
  });

  it('renders the compare panel with an explicit per-field verdict table', async () => {
    const { container } = panel();
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 cover.png' })).toBeTruthy());
    click(container, '选择素材 cover.png');
    await waitFor(() => expect(text(container)).toContain('打开版本对比'));
    click(container, '打开版本对比');
    await waitFor(() => expect(text(container)).toContain('逐字段差异'));
    expect(text(container)).toContain('对比只显示老 / 新版本的差异');
    expect(text(container)).toContain('只有你在各自模块里明确选择');
  });

  it('starts no playback by itself: audio and video previews stay user-started', async () => {
    const { container } = panel();
    await waitFor(() => expect(inTree(container).getByRole('button', { name: '选择素材 theme.mp3' })).toBeTruthy());
    click(container, '选择素材 theme.mp3');
    await waitFor(() => expect(text(container)).toContain('传给其他模块'));
    click(container, '打开版本对比');
    await waitFor(() => expect(text(container)).toContain('版本对比'));
    const compare = inTree(container).getByRole('region', { name: '版本对比' });
    // 初始没有活动播放槽，也没有任何 <audio>/<video> 元素被创建。
    expect(within(compare).queryByText(/停止播放/)).toBeNull();
    expect(compare.querySelectorAll('audio, video')).toHaveLength(0);
    expect(within(compare).getByText(/需你主动开始/)).toBeTruthy();
  });
});

