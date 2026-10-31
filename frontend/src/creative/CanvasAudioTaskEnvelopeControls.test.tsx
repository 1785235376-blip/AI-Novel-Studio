// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CanvasAudioTaskEnvelopeControls } from './CanvasAudioTaskEnvelopeControls';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const values = { gain_db: '', fade_in_ms: '', fade_out_ms: '' };
const labels = ['本任务增益（-60–12 dB，可选）', '本任务淡入时长（毫秒，可选）', '本任务淡出时长（毫秒，可选）'];
const input = (index: number) => screen.getByLabelText(labels[index]) as HTMLInputElement;
const retainedChange = (index: number) => {
  const element = input(index);
  return (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onChange as
    (event: { target: { value: string } }) => void;
};

it('shows only three bounded task fields with honest processing and unknown-cost copy', () => {
  const onChange = vi.fn(), network = vi.fn(); vi.stubGlobal('fetch', network);
  const view = render(<CanvasAudioTaskEnvelopeControls values={values} disabled={false} isCurrent={() => true} onChange={onChange} />);
  expect(screen.getAllByRole('spinbutton')).toHaveLength(3);
  expect(input(0).min).toBe('-60'); expect(input(0).max).toBe('12'); expect(input(0).step).toBe('any');
  for (const index of [1, 2]) { expect(input(index).min).toBe('0'); expect(input(index).max).toBe('120000'); expect(input(index).step).toBe('1'); }
  expect(screen.getByText(/先应用增益，再在线性幅度上淡入淡出/)).toBeTruthy();
  expect(screen.getByText(/48 kHz、双声道 PCM16 WAV/)).toBeTruthy();
  expect(screen.getByRole('status').textContent).toContain('费用未估算');
  expect(screen.queryByRole('button')).toBeNull();
  view.rerender(<CanvasAudioTaskEnvelopeControls values={{ gain_db: '-6', fade_in_ms: '200', fade_out_ms: '300' }} disabled={false} isCurrent={() => true} onChange={onChange} />);
  expect(input(0).value).toBe('-6'); expect(input(1).value).toBe('200'); expect(input(2).value).toBe('300');
  expect(onChange).not.toHaveBeenCalled(); expect(network).not.toHaveBeenCalled();
});

it.each([['gain_db', '-6.25'], ['fade_in_ms', '0'], ['fade_out_ms', '300']] as const)(
  'emits only the explicitly edited %s string', (key, value) => {
    const onChange = vi.fn(); render(<CanvasAudioTaskEnvelopeControls values={values} disabled={false} isCurrent={() => true} onChange={onChange} />);
    fireEvent.change(input(['gain_db', 'fade_in_ms', 'fade_out_ms'].indexOf(key)), { target: { value } });
    expect(onChange).toHaveBeenCalledTimes(1); expect(onChange).toHaveBeenCalledWith(key, value);
  });

it('preserves clearing as omission input and never inserts a zero default', () => {
  const onChange = vi.fn(); render(<CanvasAudioTaskEnvelopeControls values={{ ...values, gain_db: '0' }} disabled={false} isCurrent={() => true} onChange={onChange} />);
  fireEvent.change(input(0), { target: { value: '' } });
  expect(onChange).toHaveBeenCalledTimes(1); expect(onChange).toHaveBeenCalledWith('gain_db', '');
});

it('guards stale, disabled, replaced and unmounted callbacks, including delayed delivery', () => {
  let current = true; const first = vi.fn(), second = vi.fn(), isCurrent = () => current;
  const view = render(<CanvasAudioTaskEnvelopeControls values={values} disabled={false} isCurrent={isCurrent} onChange={first} />);
  const old = retainedChange(0); current = false;
  act(() => old({ target: { value: '-6' } })); expect(first).not.toHaveBeenCalled(); current = true;
  view.rerender(<CanvasAudioTaskEnvelopeControls values={values} disabled isCurrent={isCurrent} onChange={first} />);
  act(() => old({ target: { value: '-6' } }));
  const disabled = retainedChange(0); act(() => disabled({ target: { value: '-6' } }));
  view.rerender(<CanvasAudioTaskEnvelopeControls values={values} disabled={false} isCurrent={isCurrent} onChange={second} />);
  act(() => old({ target: { value: '-6' } })); expect(first).not.toHaveBeenCalled(); expect(second).not.toHaveBeenCalled();
  fireEvent.change(input(0), { target: { value: '-3' } }); expect(second).toHaveBeenCalledTimes(1); expect(second).toHaveBeenCalledWith('gain_db', '-3');
  const retired = retainedChange(1); view.unmount(); act(() => retired({ target: { value: '100' } }));
  expect(second).toHaveBeenCalledTimes(1);
});

it('retires a used render before another retained callback in the same batch', () => {
  const onChange = vi.fn(); render(<CanvasAudioTaskEnvelopeControls values={values} disabled={false} isCurrent={() => true} onChange={onChange} />);
  const first = retainedChange(0), second = retainedChange(1);
  act(() => { first({ target: { value: '0' } }); second({ target: { value: '100' } }); });
  expect(onChange).toHaveBeenCalledTimes(1); expect(onChange).toHaveBeenCalledWith('gain_db', '0');
});

it('works in StrictMode and retires callbacks after a newer committed value render', () => {
  const onChange = vi.fn(), props = { disabled: false, isCurrent: () => true, onChange };
  const view = render(<StrictMode><CanvasAudioTaskEnvelopeControls {...props} values={values} /></StrictMode>);
  const old = retainedChange(0);
  view.rerender(<StrictMode><CanvasAudioTaskEnvelopeControls {...props} values={{ ...values, gain_db: '-2' }} /></StrictMode>);
  act(() => old({ target: { value: '-6' } })); expect(onChange).not.toHaveBeenCalled();
  fireEvent.change(input(0), { target: { value: '-1' } }); expect(onChange).toHaveBeenCalledTimes(1); expect(onChange).toHaveBeenCalledWith('gain_db', '-1');
});
