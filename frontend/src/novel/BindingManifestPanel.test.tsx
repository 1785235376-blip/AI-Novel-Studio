// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { BindingManifestPanel } from './BindingManifestPanel';

describe('BindingManifestPanel', () => {
  it('renders bindings and removes one item', () => {
    const onRemove = vi.fn();
    render(<BindingManifestPanel manifest={{ characters: ['主角'], scenes: ['车站'], props: [], updatedAt: '' }} onRemove={onRemove} />);
    fireEvent.click(screen.getByLabelText('移除角色绑定 主角'));
    expect(onRemove).toHaveBeenCalledWith('characters', '主角');
  });
});
