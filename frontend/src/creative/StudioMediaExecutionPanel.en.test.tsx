// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-EN] Lock EN surface for StudioMediaExecutionPanel + CanvasImageNodeTask residual copy. */
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setLocale, translateZh } from '../i18n';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { mediaProviderKey, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { MediaOperation, ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { cutoutAssets } from './studioCpuCutout.testFixtures';

const HAN = /[\u4e00-\u9fff]/;
const digest = 'a'.repeat(64);
const source = cutoutAssets()[0];
const row = (local: boolean, operation: MediaOperation = 'm5.image.t2i'): ProductionProvider => ({
  operation_id: operation, provider_id: local ? 'local-config' : 'cloud-config', model_id: 'configured-model', local,
  route_digest: digest, capability: 'IMAGE', supported_parameters: ['seed', 'width'], readiness: 'CONFIGURED_NOT_VERIFIED',
});

beforeEach(() => { cleanup(); localStorage.clear(); act(() => setLocale('en')); });
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });

describe('VERA-EN translateZh locks for media panel / image node residuals', () => {
  it('error and notice strings from CanvasImageNodeTask have English entries', () => {
    for (const s of [
      '创建记录已由其他窗口改变；保留原请求，不会创建或入队。',
      '原节点、项目、权限或未确认操作已改变，请关闭后重新核对；不会重新发送。',
      '当前项目代次或写入权限未确认，原草稿保留。',
      '原任务入队意图已改变，不能恢复其他请求。',
      '本浏览器的创建意图已改变，不能继续原请求。',
      '原创建请求或读取已退役。',
      '读取或创建超时，结果仍待核对；不会重发。',
      '请先填写有效的原节点提示词。',
      '原创建记录缺失。',
      '已保存空白作品位置；尚未入队或生成，节点图与连线仍是浏览器草稿。',
      '正式节点位置准备失败。',
      '操作结果待核对。当前实例只可读取，不会自动重发；原输入与请求 ID 保留。',
      '原身份、权限或节点已改变。请取消选择后重新选择节点并打开入口；旧确认不会恢复。',
      '服务端节点资产关联',
      '画布及节点',
      '保存坐标',
      '保存来源提示词摘要',
      '原生产任务',
      '当前会话保留的入队输入',
      '入队时原提示词',
    ]) {
      const out = translateZh('en', s);
      expect(HAN.test(out), `${s} -> ${out}`).toBe(false);
    }
  });

  it('panel labels, status, handoff and gate copy have English entries', () => {
    for (const s of [
      '操作结果尚未确认，已阻止继续发送。请读取原任务核对；不会自动重试。',
      '当前版本已有发送记录。相同动作不会再次发送，请继续读取原记录核对。',
      '素材引用交接到', '制作', '核对', '交接版本', '明确加入', '制作草稿', '取消', '交接',
      '媒体制作输入', '重新读取配置', '读取制作预览', '仅创建任务并入队', '任务记录', '读取任务列表',
      '配置参考不代表服务已验证可用。', '当前操作暂无', '配置；可以切换路线或先完成对应配置，不会自动回退。',
      '图片', '视频', '音频', '本地', '云端',
      '抠图交付格式（可选）', '本地平稳噪声降噪（可选）',
      '默认 PNG，保持原请求', '无损 WebP · 保留透明像素',
      '确认本次允许将提示词及选中的参考素材发送到该云端服务，可能产生费用',
      '已核对本次输入、来源和处理边界', '制作预览确认', '确认本次预览',
      '显示第', '层', '第', '层透明度（0–255）',
      '参考权重 · ', '未指定用途',
      '已加入原视频制作草稿；旧制作预览与云端确认已清除。尚未预检、入队或执行。',
      '已加入原图片制作草稿；旧制作预览与云端确认已清除。尚未预检、入队或执行。',
    ]) {
      const out = translateZh('en', s);
      expect(HAN.test(out), `${s} -> ${out}`).toBe(false);
    }
  });
});

describe('VERA-EN StudioMediaExecutionPanel visible surface', () => {
  it('renders without Chinese when locale is en', async () => {
    const providers = vi.fn().mockResolvedValue([row(true), row(false)]);
    const client = {
      providers, preview: vi.fn(), create: vi.fn(), execute: vi.fn(), get: vi.fn(), list: vi.fn().mockResolvedValue([]),
    } as unknown as StudioProductionClient;
    const props: StudioMediaExecutionProps = {
      client, assets: [source], canMutate: true, canReview: true, busy: false, isCurrent: () => true,
      read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(),
    };
    const { container } = render(<StudioMediaExecutionPanel {...props} />);
    await waitFor(() => expect(providers).toHaveBeenCalled());
    // Wait until reload button is enabled (providers settled)
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /Reload configs|重新读取配置/i });
      expect((btn as HTMLButtonElement).disabled).toBe(false);
    });
    const text = (container.textContent || '') + ' ' +
      [...container.querySelectorAll('[aria-label],[title],[placeholder]')].map(n =>
        ['aria-label', 'title', 'placeholder'].map(a => n.getAttribute(a) || '').join(' ')).join(' ');
    const hits = text.match(/[\u4e00-\u9fff]+/g) || [];
    expect(hits, hits.join('|')).toEqual([]);
    // sanity: English button present
    expect(screen.getByRole('button', { name: /Reload configs/i })).toBeTruthy();
  });
});
