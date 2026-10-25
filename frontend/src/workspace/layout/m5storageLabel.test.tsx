// @vitest-environment jsdom
// [HERMIA-FE-20261025 M5-fix] Repro: storage arrives after mount (identity resolved by bootstrap). The toolbar kept
// saying "布局仅在本次会话有效（无本地存储）" while layout was in fact loaded from / saved to local storage.
import {describe, it, expect, afterEach} from 'vitest';
import {render, screen, cleanup} from '@testing-library/react';
import {DockLayout} from './DockLayout';
import {SPECS, SCOPE, VP, MemStorage} from './testSpecs';

afterEach(cleanup);
describe('M5 storage label', () => {
  it('drops the session-only label once storage becomes available', () => {
    const r = render(<DockLayout specs={SPECS} scope={{userId: 'local', projectId: 'preview', projectInstanceId: 'preview'}} storage={null} viewport={VP} renderPanel={id => <p>{id}</p>} />);
    expect(screen.queryByText('布局仅在本次会话有效（无本地存储）')).not.toBeNull();
    r.rerender(<DockLayout specs={SPECS} scope={SCOPE} storage={new MemStorage()} viewport={VP} renderPanel={id => <p>{id}</p>} />);
    expect(screen.queryByText('布局仅在本次会话有效（无本地存储）')).toBeNull();
  });
  it('shows the session-only label when storage goes away', () => {
    const s = new MemStorage();
    const r = render(<DockLayout specs={SPECS} scope={SCOPE} storage={s} viewport={VP} renderPanel={id => <p>{id}</p>} />);
    expect(screen.queryByText('布局仅在本次会话有效（无本地存储）')).toBeNull();
    r.rerender(<DockLayout specs={SPECS} scope={{userId: 'local', projectId: 'preview', projectInstanceId: 'preview'}} storage={null} viewport={VP} renderPanel={id => <p>{id}</p>} />);
    expect(screen.queryByText('布局仅在本次会话有效（无本地存储）')).not.toBeNull();
  });
});
