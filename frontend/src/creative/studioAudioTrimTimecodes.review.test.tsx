// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';
import { StudioAudioTrimTimecodes } from './StudioAudioTrimTimecodes';
import { parseAudioTrimTimecode } from './studioAudioTrimTimecode';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { audioAssets } from './studioAudioWav.testFixtures';
import type { StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { StudioProductionClient } from './studioProductionClient';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const set = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const apply = () => screen.getByRole('button', { name: '填入起止毫秒' }) as HTMLButtonElement;
const values = () => ['来源起点（毫秒）', '来源终点（毫秒）'].map(name => (screen.getByLabelText(name) as HTMLInputElement).value);
// Retain the real handler to reproduce delayed delivery after the DOM is retired.
const oldClick = () => { const button = apply(); return (button as any)[Object.keys(button).find(key => key.startsWith('__reactProps$'))!].onClick as () => void; };
function mountOwner() {
  const api = { providers: vi.fn(async () => []), preview: vi.fn(), create: vi.fn(), action: vi.fn() };
  const assets = audioAssets(); assets.push({ ...assets[0], id: 'audio-other', filename: 'other.wav', version: 4, sha256: 'b'.repeat(64) });
  const network = vi.fn(); vi.stubGlobal('fetch', network);
  const props: StudioMediaExecutionProps = { client: api as unknown as StudioProductionClient, assets, canMutate: true, canReview: true,
    busy: false, isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn() };
  const view = render(<StudioMediaExecutionPanel {...props} />);
  return { api, network, props, view };
}
async function choose() {
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  set('操作', 'm8.audio.trim'); fireEvent.click(screen.getByLabelText('source.wav · v2'));
  set('来源起点（毫秒）', '100'); set('来源终点（毫秒）', '600');
}

it('audio1 invalid/equal/reversed/out-of-bound timecodes emit nothing; exact boundary and fractional ms are explicit only', () => {
  const onApply = vi.fn(); render(<StudioAudioTrimTimecodes start="100" end="600" disabled={false} onApply={onApply} />);
  for (const bad of ['1:60', '-0:01', '0:00.0001', '10:00.001', '00:10:00.001', '1e2:00', 'Infinity', '0:0']) {
    expect(parseAudioTrimTimecode(bad)).toBeNull(); set('裁剪起点时间码', '0:00'); set('裁剪终点时间码', bad);
    expect(apply().disabled).toBe(true); fireEvent.click(apply());
  }
  for (const [start, end] of [['0:01', '0:01'], ['0:02', '0:01']]) {
    set('裁剪起点时间码', start); set('裁剪终点时间码', end); expect(apply().disabled).toBe(true); fireEvent.click(apply());
  }
  expect(onApply).not.toHaveBeenCalled();
  set('裁剪起点时间码', '9:59.999'); set('裁剪终点时间码', '00:10:00');
  expect(onApply).not.toHaveBeenCalled(); fireEvent.click(apply());
  expect(onApply).toHaveBeenCalledWith('599999', '600000'); expect(onApply).toHaveBeenCalledTimes(1);
});

it('audio2 explicit Apply uses the original owner millisecond fields without preview, queue, execute or network', async () => {
  const f = mountOwner(); await choose();
  set('裁剪起点时间码', '0:00.125'); set('裁剪终点时间码', '0:00.625');
  expect(values()).toEqual(['100', '600']); fireEvent.click(apply()); expect(values()).toEqual(['125', '625']);
  expect(f.props.onDirtyChange).toHaveBeenCalledWith(true);
  for (const fn of [f.api.preview, f.api.create, f.api.action, f.network]) expect(fn).not.toHaveBeenCalled();
});

it('audio3 retired helper callbacks must not overwrite newer raw ranges or another selected source', async () => {
  const observations = [];
  for (const kind of ['range', 'source']) {
    const f = mountOwner(); await choose();
    set('裁剪起点时间码', '0:00.125'); set('裁剪终点时间码', '0:00.625');
    const originalButton = apply(), retained = oldClick();
    if (kind === 'range') { set('来源起点（毫秒）', '200'); set('来源终点（毫秒）', '800'); }
    else fireEvent.click(screen.getByLabelText('other.wav · v4'));
    const before = values(), remounted = apply() !== originalButton;
    act(() => retained()); const after = values();
    observations.push({ kind, remounted, before, after, source_other_selected: (screen.getByLabelText('other.wav · v4') as HTMLInputElement).checked,
      writes: f.network.mock.calls.length + f.api.create.mock.calls.length + f.api.action.mock.calls.length });
    f.view.unmount();
  }
  console.info(JSON.stringify(observations));
  expect(observations.every(row => row.remounted && JSON.stringify(row.before) === JSON.stringify(row.after))).toBe(true);
});

it('retires earlier scratch-input callbacks without rejecting the latest valid input', () => {
  const onApply = vi.fn(); render(<StudioAudioTrimTimecodes start="100" end="600" disabled={false} onApply={onApply} />);
  set('裁剪起点时间码', '0:00.125'); set('裁剪终点时间码', '0:00.625');
  const retained = oldClick();
  set('裁剪起点时间码', '0:00.200'); set('裁剪终点时间码', '0:00.800');
  act(() => retained()); expect(onApply).not.toHaveBeenCalled();
  fireEvent.click(apply()); expect(onApply).toHaveBeenCalledWith('200', '800'); expect(onApply).toHaveBeenCalledTimes(1);
});

it('retires disabled and replaced-owner callbacks while keeping the current owner usable', () => {
  const first = vi.fn(), second = vi.fn();
  const view = render(<StudioAudioTrimTimecodes start="100" end="600" disabled={false} onApply={first} />);
  const retained = oldClick();
  view.rerender(<StudioAudioTrimTimecodes start="100" end="600" disabled onApply={first} />);
  act(() => retained()); expect(first).not.toHaveBeenCalled();
  view.rerender(<StudioAudioTrimTimecodes start="100" end="600" disabled={false} onApply={second} />);
  act(() => retained()); expect(first).not.toHaveBeenCalled(); expect(second).not.toHaveBeenCalled();
  fireEvent.click(apply()); expect(second).toHaveBeenCalledWith('100', '600'); expect(second).toHaveBeenCalledTimes(1);
});

it('keeps StrictMode Apply active and retires it on unmount', () => {
  const onApply = vi.fn();
  const view = render(<StrictMode><StudioAudioTrimTimecodes start="100" end="600" disabled={false} onApply={onApply} /></StrictMode>);
  fireEvent.click(apply()); expect(onApply).toHaveBeenCalledWith('100', '600'); expect(onApply).toHaveBeenCalledTimes(1);
  set('裁剪终点时间码', '0:00.700'); const retained = oldClick(); view.unmount();
  act(() => retained()); expect(onApply).toHaveBeenCalledTimes(1);
});

it('rejects retained Apply in the same event batch as newer owner edits', async () => {
  for (const kind of ['range', 'source']) {
    const f = mountOwner(); await choose();
    set('裁剪起点时间码', '0:00.125'); set('裁剪终点时间码', '0:00.625'); const retained = oldClick();
    act(() => {
      if (kind === 'range') { set('来源起点（毫秒）', '200'); set('来源终点（毫秒）', '800'); }
      else fireEvent.click(screen.getByLabelText('other.wav · v4'));
      retained();
    });
    expect(values()).toEqual(kind === 'range' ? ['200', '800'] : ['100', '600']);
    expect(f.network).not.toHaveBeenCalled(); expect(f.api.create).not.toHaveBeenCalled(); expect(f.api.action).not.toHaveBeenCalled();
    f.view.unmount();
  }
});
