// @vitest-environment jsdom
// [HERMIA-FE-20261025 AUDIO-T] Requires patches/audio-wiring.patch (TasksPanelLive media filter). Evidence: mock (jsdom + fake readers).
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {TasksPanelLive} from '../panels/TasksPanelLive';
import {createScopeLease} from '../state/scopeLease';
import {TaskFeed} from '../tasks/taskFeed';
import {job, D} from '../results/u4.fixtures';

afterEach(cleanup);
describe('audio filter in the shared task panel', () => {
  it('filters the SAME list locally, says it is local, issues no extra read, no raw ids', async () => {
    const list = vi.fn(async () => [job(), job({owner: 'audio', id: 'aj-1', operation_id: 'm8.audio.music', status: 'AWAITING_REVIEW', output_candidate: {id: 'asset-a', version: 1, digest: D('e'), kind: 'audio'}} as never)]);
    const feed = new TaskFeed({production: {list, get: vi.fn()}}, createScopeLease('A'));
    render(<TasksPanelLive feed={feed} navigator={null} active hasNode={() => false} captureReturn={() => ({panelId: 'tasks', canvas: 'creative', nodeIds: [], focusTestId: 'x', viewport: null})}
      onLocate={() => {}} onOpenExecution={() => {}} onReturn={() => {}} />);
    await act(async () => {});
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    fireEvent.click(screen.getByTestId('aud-filter-audio'));
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(1); expect(items[0].textContent).toBe('音频任务 · 等待审核');
    expect(screen.getByTestId('aud-filter-gap').textContent).toBe('服务端任务列表不能按媒介筛选：这里只是在已读取的列表里挑出音频任务。');
    expect(screen.getByTestId('aud-filter-audio').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('aud-filter-all'));
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(list).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('u3-tasks').textContent).not.toMatch(/aj-1|asset-a|m8\./);
  });
});
