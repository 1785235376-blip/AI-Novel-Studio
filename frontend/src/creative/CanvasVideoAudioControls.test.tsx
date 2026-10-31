// @vitest-environment jsdom
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {CanvasVideoAudioControls} from './CanvasVideoAudioControls';

afterEach(cleanup);

describe('video-card source audio control', () => {
  it.each([false, true])('renders the caller’s %s value without dispatching anything', value => {
    const onChange = vi.fn();
    render(<CanvasVideoAudioControls value={value} disabled={false} isCurrent={() => true} onChange={onChange}/>);
    expect((screen.getByRole('checkbox', {name: '保留源音轨'}) as HTMLInputElement).checked).toBe(value);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/第一音轨/).textContent).toContain('重新编码为 AAC');
    expect(screen.getByText(/第一音轨/).textContent).toContain('不是无损复制');
    expect(screen.getByText(/第一音轨/).textContent).toContain('关闭后输出静音');
    expect(screen.getByRole('status').textContent).toContain('不代表验证通过或执行许可');
  });
  it('emits only the user’s boolean choice', () => {
    const onChange = vi.fn();
    const {rerender} = render(<CanvasVideoAudioControls value={false} disabled={false} isCurrent={() => true} onChange={onChange}/>);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange.mock.calls).toEqual([[true]]);
    rerender(<CanvasVideoAudioControls value={true} disabled={false} isCurrent={() => true} onChange={onChange}/>);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange.mock.calls).toEqual([[true], [false]]);
  });
  it.each(['disabled', 'stale'])('disables an unavailable %s form and refuses synthetic events', mode => {
    const onChange = vi.fn();
    render(<CanvasVideoAudioControls value={false} disabled={mode === 'disabled'} isCurrent={() => mode !== 'stale'} onChange={onChange}/>);
    expect((screen.getByRole('group') as HTMLFieldSetElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange).not.toHaveBeenCalled();
  });
  it('rechecks a source that becomes stale after rendering', () => {
    let current = true;
    const onChange = vi.fn();
    render(<CanvasVideoAudioControls value={false} disabled={false} isCurrent={() => current} onChange={onChange}/>);
    current = false;
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange).not.toHaveBeenCalled();
  });
  it('has a unique accessible explanation for each task', () => {
    render(<><CanvasVideoAudioControls value={false} disabled={false} isCurrent={() => true} onChange={() => undefined}/>
      <CanvasVideoAudioControls value={true} disabled={true} isCurrent={() => true} onChange={() => undefined}/></>);
    const ids = screen.getAllByRole('checkbox').map(input => input.getAttribute('aria-describedby'));
    expect(ids[0]).toBeTruthy(); expect(ids[0]).not.toBe(ids[1]);
    for (const id of ids) expect(document.getElementById(id!)?.textContent).toContain('第一音轨');
  });
});
