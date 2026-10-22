// @vitest-environment jsdom
// [HERMIA-FE-20261022 REBUILD-SHELL]
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { Popover, Drawer, StateTag } from './primitives';
import { rbError } from './rebuildApi';
import { ApiError } from '../api';
afterEach(cleanup);
describe('rebuild shell primitives', () => {
  it('popover toggles and closes on Escape', () => {
    render(<Popover label="任务">{() => <p>内容</p>}</Popover>);
    fireEvent.click(screen.getByRole('button', { name: '任务' }));
    expect(screen.getByRole('dialog', { name: '任务' })).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
  it('drawer close calls onClose', () => {
    const onClose = vi.fn(); render(<Drawer title="资料" onClose={onClose}><p>x</p></Drawer>);
    fireEvent.click(screen.getByRole('button', { name: '关闭资料' })); expect(onClose).toHaveBeenCalled();
  });
  it('state tag exposes tone', () => { render(<StateTag tone="err">失败</StateTag>); expect(screen.getByText('失败').getAttribute('data-tone')).toBe('err'); });
  it('rbError is honest', () => {
    expect(rbError(new TypeError('fetch'))).toContain('后端不可用');
    expect(rbError(new ApiError({ status: 404, code: 'HTTP_ERROR', message: 'x' } as any))).toContain('404');
    expect(rbError(new ApiError({ status: 409, code: 'EXPERIMENTAL_FEATURE_DISABLED', message: 'x' } as any))).toContain('实验开关');
  });
});
