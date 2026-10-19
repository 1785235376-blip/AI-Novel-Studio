// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { BailianPresetPanel } from './BailianPresetPanel';
import wire from './bailianPresetWire.testFixture.json';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
const endpoint = '/api/model-center/provider-presets/bailian-text';
function setup(read: () => Promise<unknown> = async () => structuredClone(wire)) {
  const calls = vi.fn(async (url: string, method: string) => {
    if (url !== endpoint || method !== 'GET') throw new Error('Only the existing public preset read is allowed');
    return read();
  });
  return { calls, props: { projectId: 'project', transport: { json: calls } as unknown as StudioGraphTransport,
    identity: 'scope', active: true, denied: false, busy: false, isCurrent: () => true,
    read: async <T,>(work: () => Promise<T>) => work() } };
}
const readButton = () => screen.getByRole('button', { name: '明确读取百炼文本预设' });
const checkButton = () => screen.getByRole('button', { name: '本地预检端点与模型 ID（不连接）' });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('checks the existing regional endpoint and model syntax without another request or persistence', async () => {
  const { calls, props } = setup(); const writes = vi.spyOn(Storage.prototype, 'setItem');
  render(<BailianPresetPanel {...props} />); expect(calls).not.toHaveBeenCalled();
  fireEvent.click(readButton()); await screen.findByLabelText('百炼 API 地区');
  fireEvent.click(checkButton()); expect(screen.getByText('请先按实际 API 账户选择地区。')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('百炼 API 地区'), { target: { value: 'cn-hongkong' } });
  fireEvent.click(checkButton()); expect(screen.getByText('请填写账户中实际可用的文本模型 ID。')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('百炼文本模型 ID'), { target: { value: 'model with spaces' } });
  fireEvent.click(checkButton()); expect(screen.getByText(/模型 ID 格式无效/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('百炼文本模型 ID'), { target: { value: 'synthetic-model' } });
  expect(screen.queryByText(/模型 ID 格式无效/)).toBeNull();
  fireEvent.click(checkButton()); expect(screen.getByText('本地格式预检通过（未连接）')).toBeTruthy();
  expect(screen.getByText(/未验证模型存在、账户权限、额度或实际推理/)).toBeTruthy();
  expect((screen.getByLabelText('手动主机配置预览（未应用）') as HTMLTextAreaElement).value).toBe('ALIYUN_BAILIAN_REGION=cn-hongkong\nALIYUN_BAILIAN_MODEL=synthetic-model');
  fireEvent.change(screen.getByLabelText('百炼 API 地区'), { target: { value: 'cn-beijing' } });
  expect(screen.queryByText('本地格式预检通过（未连接）')).toBeNull();
  expect(calls).toHaveBeenCalledTimes(1); expect(writes).not.toHaveBeenCalled();
});

it.each<[number, string]>([
  [401, '宿主会话需要重新登录'], [403, '当前会话没有预设读取权限'],
  [404, '当前宿主尚未提供百炼预设'], [409, '项目或分支上下文已变化'],
  [429, '宿主请求受到限流'], [503, '宿主预设服务暂不可用'],
])('classifies host preset HTTP %s without showing raw error bodies or retrying', async (status, title) => {
  const { calls, props } = setup(async () => { throw new ApiError({ status, code: 'SYNTHETIC_UNTRUSTED_CODE', message: 'SYNTHETIC_SECRET_MUST_NOT_RENDER', details: { api_key: 'SYNTHETIC_ONLY' } }); });
  const view = render(<BailianPresetPanel {...props} />); fireEvent.click(readButton());
  await screen.findByText(title); expect(screen.queryByText(/SYNTHETIC_SECRET|SYNTHETIC_UNTRUSTED/)).toBeNull();
  expect(screen.getByText(/不是百炼云端连接测试/)).toBeTruthy();
  view.rerender(<BailianPresetPanel {...props} />); expect(calls).toHaveBeenCalledTimes(1);
});

it('uses a fixed fallback for unknown transport errors and retries only on an explicit read', async () => {
  let fail = true;
  const { calls, props } = setup(async () => { if (fail) throw new TypeError('SYNTHETIC_RAW_TRANSPORT_BODY'); return structuredClone(wire); });
  render(<BailianPresetPanel {...props} />); fireEvent.click(readButton());
  await screen.findByText('宿主预设读取未完成'); expect(screen.queryByText(/SYNTHETIC_RAW_TRANSPORT_BODY/)).toBeNull();
  expect(calls).toHaveBeenCalledTimes(1); fail = false;
  fireEvent.click(readButton()); await screen.findByLabelText('百炼 API 地区');
  expect(calls).toHaveBeenCalledTimes(2); expect(screen.queryByText('宿主预设读取未完成')).toBeNull();
});

it('retires local checks on A-B-A, denial and activation changes without an automatic read', async () => {
  const { calls, props } = setup(); const view = render(<BailianPresetPanel {...props} />);
  fireEvent.click(readButton()); await screen.findByLabelText('百炼 API 地区');
  fireEvent.change(screen.getByLabelText('百炼 API 地区'), { target: { value: 'cn-beijing' } });
  fireEvent.change(screen.getByLabelText('百炼文本模型 ID'), { target: { value: 'synthetic-model' } }); fireEvent.click(checkButton());
  view.rerender(<BailianPresetPanel {...props} identity="B" />); view.rerender(<BailianPresetPanel {...props} />);
  expect(screen.queryByLabelText('百炼 API 地区')).toBeNull(); expect(screen.queryByText('本地格式预检通过（未连接）')).toBeNull();
  view.rerender(<BailianPresetPanel {...props} denied />); expect(screen.queryByRole('button')).toBeNull();
  view.rerender(<BailianPresetPanel {...props} active={false} />); view.rerender(<BailianPresetPanel {...props} />);
  expect(screen.queryByLabelText('百炼 API 地区')).toBeNull(); expect(calls).toHaveBeenCalledTimes(1);
});

it('does not display a late failure after project identity returns to A', async () => {
  let reject!: (reason: unknown) => void;
  const { calls, props } = setup(() => new Promise((_resolve, fail) => { reject = fail; }));
  const view = render(<BailianPresetPanel {...props} />); fireEvent.click(readButton());
  view.rerender(<BailianPresetPanel {...props} identity="B" />); view.rerender(<BailianPresetPanel {...props} />);
  await act(async () => reject(new ApiError({ status: 503, code: 'SYNTHETIC', message: 'SYNTHETIC_LATE_BODY' })));
  expect(screen.queryByText('宿主预设服务暂不可用')).toBeNull(); expect(screen.queryByText(/SYNTHETIC_LATE_BODY/)).toBeNull(); expect(calls).toHaveBeenCalledTimes(1);
});

it('rejects an untrusted preset response without showing its endpoint or private fields', async () => {
  const { calls, props } = setup(async () => ({ ...wire, private_debug: 'SYNTHETIC_PRIVATE_RESPONSE' }));
  render(<BailianPresetPanel {...props} />); fireEvent.click(readButton());
  await screen.findByText('宿主预设响应无法核验');
  expect(screen.queryByText(/SYNTHETIC_PRIVATE_RESPONSE/)).toBeNull();
  expect(screen.queryByLabelText('百炼 API 地区')).toBeNull(); expect(calls).toHaveBeenCalledTimes(1);
});

it('a retained precheck handler checks the latest draft and cannot bypass busy state', async () => {
  const { props } = setup(); const view = render(<BailianPresetPanel {...props} />);
  fireEvent.click(readButton()); await screen.findByLabelText('百炼 API 地区');
  fireEvent.change(screen.getByLabelText('百炼 API 地区'), { target: { value: 'cn-beijing' } });
  fireEvent.change(screen.getByLabelText('百炼文本模型 ID'), { target: { value: 'valid-synthetic' } });
  const button = checkButton();
  const handler = (button as unknown as Record<string, { onClick: () => void }>)[Object.keys(button).find(key => key.startsWith('__reactProps'))!].onClick;
  fireEvent.change(screen.getByLabelText('百炼文本模型 ID'), { target: { value: 'invalid model' } });
  act(handler); expect(screen.getByText(/模型 ID 格式无效/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('百炼文本模型 ID'), { target: { value: 'valid-synthetic' } });
  view.rerender(<BailianPresetPanel {...props} busy />); act(handler);
  expect(screen.queryByText('本地格式预检通过（未连接）')).toBeNull();
});
