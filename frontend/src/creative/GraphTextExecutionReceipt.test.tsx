// @vitest-environment jsdom
import { createHash } from 'node:crypto';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GraphTextAssetSummary } from './GraphTextAssetSummary';
import { graphTextAssetOutput } from './studioGraphTextAssetContract';
import { storedTextAsset } from './studioGraphTextAsset.testFixtures';
import { textExecutionReceiptRun } from './studioGraphTextExecutionReceipt.testFixtures';

afterEach(cleanup);
describe('TextAsset execution evidence in the existing receipt area', () => {
  it('leaves old receipts visible without inventing missing execution evidence', () => {
    render(<GraphTextAssetSummary output={storedTextAsset()} />);
    expect(screen.getByRole('region', { name: '私有文字资产回执' })).toBeTruthy();
    expect(screen.getByText('核对文字资产来源')).toBeTruthy();
    expect(screen.queryByText('核对文字执行回执')).toBeNull();
    expect(screen.queryByText(/真实本地模型/)).toBeNull();
  });
  it('shows the exact prompt, parameters, workflow, job, and terminal evidence without a new required action', () => {
    const { run, asset, receipt } = textExecutionReceiptRun();
    receipt.prompt = '  第一行 🌊\n\t第二行，保留完整输入  ';
    receipt.prompt_sha256 = createHash('sha256').update(receipt.prompt).digest('hex'); run.model_runtime!.preview!.prompt = receipt.prompt;
    const output = graphTextAssetOutput(asset, run);
    const { container } = render(<GraphTextAssetSummary output={output} />), region = screen.getByRole('region', { name: '私有文字资产回执' });
    const toggle = within(region).getByText('核对文字执行回执'); fireEvent.click(toggle);
    expect(toggle.closest('details')?.open).toBe(true);
    expect(within(region).getByText('执行模式：真实本地模型（real）')).toBeTruthy();
    expect(within(region).getByText('精确参数：temperature = 0 · max_output_tokens = 512 · stop_sequences = []')).toBeTruthy();
    expect(within(region).getByText('工作流：model_run · 图：model_graph · v1 · 来源 v4')).toBeTruthy();
    expect(within(region).getByText('模型节点：generate · 任务：original_job')).toBeTruthy();
    expect(within(region).getByText('结算：original_settlement · 2026-10-10T00:00:01Z')).toBeTruthy();
    expect(within(region).getByText('模型指纹来自 Model Center 元数据，不是完整模型文件 SHA-256。')).toBeTruthy();
    expect(within(region).getByText('运行完成：COMPLETED · 质量验收：未运行（NOT_RUN）。运行完成不代表质量通过。')).toBeTruthy();
    expect(container.querySelector('pre')?.textContent).toBe(receipt.prompt);
    expect(within(region).queryAllByRole('button')).toHaveLength(0); expect(within(region).queryAllByRole('checkbox')).toHaveLength(0);
    expect(container.querySelector('[style]')).toBeNull();
  });
  it('labels synthetic protocol results as stand-ins and never shows a real model completion label', () => {
    const { run, asset } = textExecutionReceiptRun('DRAFT', true);
    render(<GraphTextAssetSummary output={graphTextAssetOutput(asset, run)} />);
    expect(screen.getByText('执行模式：测试替身（mock_standin），不代表真实模型推理')).toBeTruthy();
    expect(screen.getByText('模型指纹仅标识合成测试协议，不是模型文件哈希。')).toBeTruthy();
    expect(screen.getByText('运行时指纹：未记录 · 版本：未记录')).toBeTruthy();
    expect(screen.queryByText('执行模式：真实本地模型（real）')).toBeNull();
  });
  it('renders prompt text literally without executing markup', () => {
    const { run, asset, receipt } = textExecutionReceiptRun();
    receipt.prompt = '<img src="x" onerror="alert(1)">\n<script>ignored()</script>'; run.model_runtime!.preview!.prompt = receipt.prompt;
    receipt.prompt_sha256 = createHash('sha256').update(receipt.prompt).digest('hex');
    const { container } = render(<GraphTextAssetSummary output={graphTextAssetOutput(asset, run)} />);
    expect(container.querySelector('pre')?.textContent).toBe(receipt.prompt);
    expect(container.querySelector('img, script')).toBeNull();
  });
});
