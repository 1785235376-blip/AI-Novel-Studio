// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { DirectorImageReviewPanel } from './DirectorImageReviewPanel';
import type { DirectorImageClient } from './directorImageClient';
import { imageAsset, imagePending, imagePreview, imageRegistration, imageReview, imageSnapshot, imageSourceDocument, imageStatus, imageTarget } from './directorImage.testFixtures';
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const consent = (label: RegExp) => fireEvent.click(screen.getByLabelText(label));
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const amount = '人工声明本地成本（microUSD，1 USD = 1000000）';
function setup() {
  const client: DirectorImageClient = { assets: vi.fn().mockResolvedValue({ items: [imageAsset] }), capabilities: vi.fn().mockResolvedValue({ enabled: true, registered_choices: [imageRegistration] }),
    list: vi.fn().mockResolvedValue({ items: [imageStatus], truncated: false }), status: vi.fn().mockResolvedValue(imageStatus), preview: vi.fn().mockResolvedValue(imagePreview),
    dispatch: vi.fn().mockResolvedValue(imageStatus), cancel: vi.fn().mockResolvedValue(undefined), prepare: vi.fn().mockResolvedValue(imagePending),
    declareCost: vi.fn().mockResolvedValue(undefined), review: vi.fn().mockResolvedValue(imageReview), adopt: vi.fn().mockResolvedValue({ proposal_id: 'proposal', target: { ...imageTarget, version: 3 }, committed: true, historical: false }) };
  const props: ComponentProps<typeof DirectorImageReviewPanel> = { client, source: imageSourceDocument, snapshot: imageSnapshot, selectionKey: 'node-a', active: true, available: true, busy: false,
    isCurrent: () => true, read: work => work(), mutate: work => work(), onPending: vi.fn(), onAdopted: vi.fn(), onDenied: vi.fn(), onOpenModels: vi.fn(), onOpenBroker: vi.fn() };
  return { client, props };
}
async function open() { click('打开图像导演审核'); await screen.findByRole('option', { name: /现有 VISION 注册/ }); }
async function preview() {
  await open(); change('图像理解原素材', 'image'); change('图像理解目标场景', 'scene'); change('VISION 注册模型', JSON.stringify(['local:vision', 'vision'])); change('图像导演指令', '我的指令');
  click('预览图像理解请求'); await screen.findByDisplayValue('私密完整提示');
}
async function dispatch() { await preview(); consent(/已核对图片、场景/); click('确认发送图像理解'); await screen.findByText(/请求已发送/); }
async function pending() { await dispatch(); click('准备图像成本审核'); await screen.findByText('私密模型描述'); }
async function review() { await dispatch(); click('读取图像人工审核内容'); await screen.findByLabelText('人工审核后的导演备注'); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
describe('mounted IMAGE review lifetime and separate explicit actions', () => {
  it('makes no mount-time request; keeps dispatch, blank cost and note adoption separate', async () => {
    const { client, props } = setup(); render(<DirectorImageReviewPanel {...props} />);
    expect(client.capabilities).not.toHaveBeenCalled(); await preview(); expect(client.dispatch).not.toHaveBeenCalled(); expect(button('确认发送图像理解').disabled).toBe(true);
    consent(/已核对图片、场景/); click('确认发送图像理解'); await screen.findByText(/请求已发送/); expect(client.dispatch).toHaveBeenCalledTimes(1); expect(client.status).not.toHaveBeenCalled();
    click('准备图像成本审核'); await screen.findByText('私密模型描述'); expect((screen.getByLabelText(amount) as HTMLInputElement).value).toBe(''); expect(client.declareCost).not.toHaveBeenCalled();
    change(amount, '0'); change('成本声明依据', '人工确认本地用量'); expect(button('提交独立成本声明').disabled).toBe(true);
    consent(/我明确声明此金额/); click('提交独立成本声明'); await screen.findByText(/已记录人工声明/);
    expect(client.declareCost).toHaveBeenCalledWith('proposal', expect.objectContaining({ expected_version: 7, declared_microusd: 0, confirmed_declaration: true, reviewed_terminal_digest: imagePending.terminal_digest }), expect.any(AbortSignal));
    expect(client.review).not.toHaveBeenCalled(); click('读取图像人工审核内容'); await screen.findByLabelText('人工审核后的导演备注');
    expect((screen.getByLabelText('人工审核后的导演备注') as HTMLTextAreaElement).value).toBe(''); consent(/建议 1：/); change('人工审核后的导演备注', '作者核对后的备注');
    expect(client.adopt).not.toHaveBeenCalled(); expect(button('采纳为一条导演备注').disabled).toBe(true); consent(/已人工核对所选建议/); click('采纳为一条导演备注');
    await waitFor(() => expect(props.onAdopted).toHaveBeenCalledTimes(1)); expect(client.adopt).toHaveBeenCalledWith('proposal', expect.objectContaining({ note: '作者核对后的备注', target: imageTarget, selected_suggestions: [0], human_review_confirmed: true }), expect.any(AbortSignal));
  });
  it('never retries a lost dispatch acknowledgment and explicitly reads the same proposal', async () => {
    const { client, props } = setup(); vi.mocked(client.dispatch).mockRejectedValue(new Error('lost')); render(<DirectorImageReviewPanel {...props} />); await preview();
    consent(/已核对图片、场景/); const send = button('确认发送图像理解'); fireEvent.click(send); fireEvent.click(send); await screen.findByText(/发送回执未确认/);
    expect(client.dispatch).toHaveBeenCalledTimes(1); expect(screen.queryByDisplayValue('私密完整提示')).toBeNull(); expect(client.status).not.toHaveBeenCalled();
    click('读取同一提案状态'); await screen.findByText(/仅核对任务元数据/); expect(client.status).toHaveBeenCalledWith('proposal', expect.any(AbortSignal)); expect(client.dispatch).toHaveBeenCalledTimes(1);
  });
  it('keeps cost/note input until explicit submission or explicit discard', async () => {
    const { client, props } = setup(); render(<DirectorImageReviewPanel {...props} />); await pending(); change(amount, '12'); change('成本声明依据', '尚未提交依据');
    for (const name of ['重新读取图像能力与素材', '读取同一提案状态', '准备图像成本审核', '读取图像人工审核内容', '预览图像理解请求']) { expect(button(name).disabled).toBe(true); click(name); }
    expect((screen.getByLabelText(amount) as HTMLInputElement).value).toBe('12'); expect(client.declareCost).not.toHaveBeenCalled();
    expect((screen.getByLabelText('图像理解目标场景').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
    consent(/放弃尚未提交的成本与备注/); click('清除未提交的审核输入'); click('读取图像人工审核内容'); await screen.findByLabelText('人工审核后的导演备注');
    change('人工审核后的导演备注', '未提交作者备注'); consent(/建议 1：/); expect(button('读取同一提案状态').disabled).toBe(true); expect(button('重新读取图像能力与素材').disabled).toBe(true);
    click('打开原 Broker 预算设置'); expect(props.onOpenBroker).toHaveBeenCalledTimes(1); expect((screen.getByLabelText('人工审核后的导演备注') as HTMLTextAreaElement).value).toBe('未提交作者备注');
    expect(client.adopt).not.toHaveBeenCalled();
  });
  it('clears old evidence before refreshing capabilities, including failed or disabled responses', async () => {
    const { client, props } = setup(); render(<DirectorImageReviewPanel {...props} />); await review();
    let finish!: (value: Awaited<ReturnType<DirectorImageClient['capabilities']>>) => void; vi.mocked(client.capabilities).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    click('重新读取图像能力与素材'); expect(screen.queryByText('私密模型描述')).toBeNull(); expect(screen.queryByLabelText('人工审核后的导演备注')).toBeNull();
    await act(async () => finish({ enabled: false, registered_choices: [] })); await screen.findByText(/图像执行能力尚未启用/); expect(screen.queryByText('私密模型描述')).toBeNull();
    expect(client.adopt).not.toHaveBeenCalled();
  });
  it.each(['active', 'available', 'client', 'selection'] as const)('rejects late preview after %s A→B→A retirement', async kind => {
    const { client, props } = setup(); let finish!: (value: typeof imagePreview) => void; vi.mocked(client.preview).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const view = render(<DirectorImageReviewPanel {...props} />); await open(); change('图像理解原素材', 'image'); change('图像理解目标场景', 'scene'); change('VISION 注册模型', JSON.stringify(['local:vision', 'vision'])); change('图像导演指令', '私密输入'); click('预览图像理解请求');
    const alternate = kind === 'selection' ? { selectionKey: 'node-b' } : kind === 'client' ? { client: setup().client } : { [kind]: false };
    view.rerender(<DirectorImageReviewPanel {...props} {...alternate} />); view.rerender(<DirectorImageReviewPanel {...props} />);
    await act(async () => finish(imagePreview)); expect(screen.queryByDisplayValue('私密完整提示')).toBeNull(); expect(screen.queryByDisplayValue('私密输入')).toBeNull(); expect(client.dispatch).not.toHaveBeenCalled();
  });
  it('fences queued work before the transport and late adoption after owner retirement', async () => {
    const { client, props } = setup(); const queue: (() => Promise<unknown>)[] = []; const view = render(<DirectorImageReviewPanel {...props} />); await preview();
    view.rerender(<DirectorImageReviewPanel {...props} mutate={work => new Promise(resolve => queue.push(() => work().then(resolve)))} />);
    consent(/已核对图片、场景/); click('确认发送图像理解'); click('关闭图像审核并清除本页内容'); await expect(Promise.resolve().then(() => queue[0]())).rejects.toMatchObject({ name: 'AbortError' }); expect(client.dispatch).not.toHaveBeenCalled();
    view.unmount(); const second = setup(); let finish!: (v: Awaited<ReturnType<DirectorImageClient['adopt']>>) => void; vi.mocked(second.client.adopt).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const adopted = render(<DirectorImageReviewPanel {...second.props} />); await review(); consent(/建议 1：/); change('人工审核后的导演备注', '人工备注'); consent(/已人工核对所选建议/); click('采纳为一条导演备注');
    adopted.rerender(<DirectorImageReviewPanel {...second.props} active={false} />); adopted.rerender(<DirectorImageReviewPanel {...second.props} />);
    await act(async () => finish({ proposal_id: 'proposal', target: { ...imageTarget, version: 3 }, historical: false, committed: true })); expect(second.props.onAdopted).not.toHaveBeenCalled();
  });
  it('reopens metadata and explicitly reviews without recreating a preview or declaring again', async () => {
    const { client, props } = setup(); render(<DirectorImageReviewPanel {...props} />); await open(); change('图像理解目标场景', 'scene'); click('读取图像提案目录'); await screen.findByRole('option', { name: /proposal · DISPATCHED/ });
    change('已保存图像提案', 'proposal'); click('读取同一提案状态'); await screen.findByText(/仅核对任务元数据/); expect(screen.queryByText('私密模型描述')).toBeNull();
    click('读取图像人工审核内容'); await screen.findByText('私密模型描述'); expect(client.preview).not.toHaveBeenCalled(); expect(client.prepare).not.toHaveBeenCalled(); expect(client.declareCost).not.toHaveBeenCalled(); expect(client.dispatch).not.toHaveBeenCalled();
  });
  it('fails closed with no VISION, distinguishes Broker admission, and clears denied private content', async () => {
    const { client, props } = setup(); vi.mocked(client.capabilities).mockResolvedValueOnce({ enabled: true, registered_choices: [] }); const view = render(<DirectorImageReviewPanel {...props} />); click('打开图像导演审核'); await screen.findByText('没有可用的 VISION 图像理解注册'); expect(button('预览图像理解请求').disabled).toBe(true); view.unmount();
    vi.mocked(client.dispatch).mockRejectedValue(new ApiError({ status: 409, code: 'DIRECTOR_IMAGE_BROKER_ADMISSION_BLOCKED', message: 'private error' })); render(<DirectorImageReviewPanel {...props} />); await preview(); consent(/已核对图片、场景/); click('确认发送图像理解'); await screen.findByText(/Broker 未准入/); expect(screen.queryByText(/发送回执未确认/)).toBeNull(); expect(screen.queryByText('private error')).toBeNull();
    vi.mocked(client.status).mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: 'private error' })); click('读取同一提案状态'); await waitFor(() => expect(props.onDenied).toHaveBeenCalled()); expect(screen.queryByDisplayValue('私密完整提示')).toBeNull();
  });
});
