// @vitest-environment jsdom
import { act, type ComponentProps } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConflictDialog } from './ConflictDialog';
import { conflictResolutionDrafts, conflicts, drafts, type PersistentConflict } from './drafts';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const value: PersistentConflict = {
  chapterId: 'chapter-1',
  local: {
    chapterId: 'chapter-1',
    content: 'local text',
    baseVersion: 1,
    updatedAt: '2026-08-10T01:00:00Z',
  },
  server: { content: 'server text', version: 2 },
  detectedAt: '2026-08-10T01:01:00Z',
};

let host: HTMLDivElement | undefined;
let root: Root | undefined;

function renderDialog(overrides: Partial<ComponentProps<typeof ConflictDialog>> = {}) {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(
    <ConflictDialog value={value} onUseServer={vi.fn()} onClose={vi.fn()} {...overrides} />,
  ));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = undefined;
  host = undefined;
  localStorage.clear();
});

describe('ConflictDialog lifecycle', () => {
  it('copies the preserved local or AI draft explicitly', async () => {
    const writeText=vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator,'clipboard',{value:{writeText},configurable:true});
    renderDialog();
    const copy=[...host!.querySelectorAll('button')].find(button=>button.textContent==='复制 AI / 本地草稿')!;
    await act(async()=>copy.click());
    expect(writeText).toHaveBeenCalledWith('local text');
    expect(host!.textContent).toContain('AI 草稿已复制。');
  });
  it('labels the modal and contains keyboard focus', () => {
    renderDialog();
    const dialog = host!.querySelector('[role="dialog"]');
    const buttons = [...host!.querySelectorAll('button')];
    const focusables = [...host!.querySelectorAll<HTMLElement>('button,textarea')];
    expect(dialog?.getAttribute('aria-modal')).toBe('true');
    expect(document.activeElement).toBe(buttons[0]);

    focusables.at(-1)!.focus();
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab', bubbles: true, cancelable: true,
    })));
    expect(document.activeElement).toBe(focusables[0]);

    act(() => document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab', shiftKey: true, bubbles: true, cancelable: true,
    })));
    expect(document.activeElement).toBe(focusables.at(-1));
  });

  it('saves a namespaced manual resolution without deleting the local draft', () => {
    drafts.save(value.local, 'branch-a');
    const onResolutionDraft = vi.fn();
    renderDialog({ namespace: 'branch-a', onResolutionDraft });
    const textarea = host!.querySelector('textarea')!;
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!;
      setter.call(textarea, 'merged text');
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const save = [...host!.querySelectorAll('button')].find(button =>
      button.textContent === '应用手工解决并保存',
    )!;
    act(() => save.click());

    expect(conflictResolutionDrafts.load(value.chapterId, 'branch-a')).toMatchObject({
      content: 'merged text', serverVersion: 2,
    });
    expect(drafts.load(value.chapterId, 'branch-a')?.content).toBe('local text');
    expect(onResolutionDraft).toHaveBeenCalledOnce();
  });

  it('uses explicit server semantics and emits the existing integration event', () => {
    const listener = vi.fn();
    addEventListener('studio:use-server-version', listener);
    const onUseServer = vi.fn();
    renderDialog({ onUseServer });
    const chooseServer = [...host!.querySelectorAll('button')].find(button =>
      button.textContent === '丢弃本地草稿并采用服务器版本',
    )!;
    act(() => chooseServer.click());

    expect(listener).toHaveBeenCalledOnce();
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toEqual({
      chapterId: value.chapterId, server: value.server,
    });
    expect(onUseServer).toHaveBeenCalledOnce();
    removeEventListener('studio:use-server-version', listener);
  });
});

describe('conflict persistence', () => {
  it('isolates drafts and resolution drafts by namespace', () => {
    drafts.save({ ...value.local, content: 'branch A' }, 'branch-a');
    drafts.save({ ...value.local, content: 'branch B' }, 'branch-b');
    conflictResolutionDrafts.save({
      chapterId: value.chapterId,
      content: 'resolution A',
      serverVersion: 2,
      sourceConflictDetectedAt: value.detectedAt,
      updatedAt: value.detectedAt,
    }, 'branch-a');

    expect(drafts.load(value.chapterId, 'branch-a')?.content).toBe('branch A');
    expect(drafts.load(value.chapterId, 'branch-b')?.content).toBe('branch B');
    expect(conflictResolutionDrafts.load(value.chapterId, 'branch-b')).toBeUndefined();
  });

  it('preserves an earlier record when a repeated conflict becomes current', () => {
    conflicts.save(value, 'branch-a');
    const repeated: PersistentConflict = {
      ...value,
      local: { ...value.local, content: 'new local', updatedAt: '2026-08-10T02:00:00Z' },
      server: { content: 'new server', version: 3 },
      detectedAt: '2026-08-10T02:01:00Z',
    };
    conflicts.save(repeated, 'branch-a');

    expect(conflicts.load(value.chapterId, 'branch-a')?.server.version).toBe(3);
    expect(conflicts.list(value.chapterId, 'branch-a')).toEqual([value]);
    conflicts.save(repeated, 'branch-a');
    expect(conflicts.list(value.chapterId, 'branch-a')).toHaveLength(1);
  });
});
