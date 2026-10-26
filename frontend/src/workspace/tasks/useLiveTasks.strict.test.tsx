// @vitest-environment jsdom
import {StrictMode, createElement, type ReactNode} from 'react';
import {describe, expect, it} from 'vitest';
import {renderHook} from '@testing-library/react';
import {useLiveTasks} from './useLiveTasks';

// [HERMIA-FE-20261025 UWPORT-S2] dev StrictMode double-effect retired the memoised lease ⇒ the drawer stuck on 正在读取任务….
describe('useLiveTasks under StrictMode', () => {
  it('ends with a current (not retired) lease after mount', () => {
    const ctx = {sessionToken: 't', actor: {id: 'u1'} as never, scope: {workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b'} as never};
    const wrapper = ({children}: {children: ReactNode}) => createElement(StrictMode, null, children);
    const r = renderHook(() => useLiveTasks('p', ctx, 'k'), {wrapper});
    expect(r.result.current.lease?.isCurrent()).toBe(true);
  });
});
