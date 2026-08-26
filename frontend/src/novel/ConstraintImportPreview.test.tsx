// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ConstraintImportPreview } from './ConstraintImportPreview';

describe('ConstraintImportPreview', () => {
  beforeEach(() => cleanup());
  it('summarizes imported shot constraint states before confirmation', () => {
    const confirm = vi.fn();
    render(<ConstraintImportPreview value={{ mode: 'video', shots: [{ constraint_status: 'confirmed' }, { constraint_status: 'pending_confirmation' }, { constraint_status: 'failed' }, {}] }} onConfirm={confirm} onCancel={vi.fn()} />);
    expect(screen.getByText('镜头约束：已确认 1 · 待确认 1 · 失败 1 · 未保存 1')).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('包含 1 个保存失败');
    fireEvent.click(screen.getByText('确认导入'));
    expect(confirm).toHaveBeenCalledTimes(1);
  });
  it('requires a second confirmation for a mismatched workspace mode', () => {
    const confirm = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<ConstraintImportPreview currentMode="image" value={{ mode: 'video', shots: [] }} onConfirm={confirm} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByText('确认导入'));
    expect(window.confirm).toHaveBeenCalled();
    expect(confirm).not.toHaveBeenCalled();
  });
});
