// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FeatureLauncher } from '../ui/FeatureLauncher';

afterEach(cleanup);
describe('Story browser navigation uses the actual launcher accessible names', () => {
  it.each(['story', 'diagnostics'])('selects Story when %s is initially active', selectedId => {
    const select = vi.fn();
    render(<FeatureLauncher selectedId={selectedId} expandedGroups={{ create: true, system: true }} onSelect={select} onToggleGroup={vi.fn()}/>);
    fireEvent.click(screen.getByRole('button', { name: '打开功能导航' }));
    const navigation = within(screen.getByRole('navigation', { name: '功能面板导航' }));
    const group = navigation.getByRole('button', { name: /^创作(?:\s*当前)?$/ });
    expect(group.getAttribute('aria-expanded')).toBe('true');
    if (selectedId === 'story') expect(group.textContent).toContain('当前');
    fireEvent.click(navigation.getByRole('button', { name: '故事资料库' }));
    expect(select).toHaveBeenCalledTimes(1);
    expect(select).toHaveBeenCalledWith('story');
  });
});
