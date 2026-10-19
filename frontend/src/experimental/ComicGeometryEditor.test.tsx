// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicGeometryEditor } from './ComicGeometryEditor';
import type { ComicDocument } from './comicLayoutsClient';
import fixture from '../../../tests/fixtures/comic_panel_duplicate.json';
const document = fixture.document as ComicDocument;
const getRevision = () => 1;
const isCurrent = () => true;
const moveButton = () => screen.getByRole('button', { name: '移动示意格框 1' });
beforeEach(() => {
  vi.stubGlobal('PointerEvent', class extends MouseEvent { pointerId: number; constructor(type: string, init: PointerEventInit) { super(type, init); this.pointerId = init.pointerId || 1; } });
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: document.width / 2, height: document.height / 2 } as DOMRect);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('projects a pointer drag without editing, then commits once on release in page pixels', () => {
  const onApply = vi.fn(); render(<ComicGeometryEditor {...{ document, getRevision, isCurrent, onApply }} disabled={false} />);
  const button = moveButton();
  fireEvent.pointerDown(button, { pointerId: 1, button: 0, clientX: 10, clientY: 10 });
  fireEvent.pointerMove(button, { pointerId: 1, clientX: 12, clientY: 14 }); expect(onApply).not.toHaveBeenCalled();
  fireEvent.pointerUp(button, { pointerId: 2, clientX: 12, clientY: 14 }); expect(onApply).not.toHaveBeenCalled();
  fireEvent.pointerUp(button, { pointerId: 1, clientX: 12, clientY: 14 });
  fireEvent.pointerUp(button, { pointerId: 1, clientX: 12, clientY: 14 });
  expect(onApply).toHaveBeenCalledTimes(1); expect(onApply.mock.calls[0][0].panels[0].x).toBe(document.panels[0].x + 4);
});
it.each(['Escape', 'pointercancel', 'lostpointercapture'])('cancels a gesture through %s', reason => {
  const onApply = vi.fn(); render(<ComicGeometryEditor {...{ document, getRevision, isCurrent, onApply }} disabled={false} />);
  const b = moveButton(); fireEvent.pointerDown(b, { button: 0, clientX: 10, clientY: 10 });
  if (reason === 'Escape') fireEvent.keyDown(b, { key: reason }); else fireEvent(b, new Event(reason, { bubbles: true }));
  fireEvent.pointerUp(b, { clientX: 20, clientY: 20 }); expect(onApply).not.toHaveBeenCalled();
});
it('keyboard supports moves, resize, acceleration and composition suppression', () => {
  const onApply = vi.fn(); render(<ComicGeometryEditor {...{ document, getRevision, isCurrent, onApply }} disabled={false} />);
  fireEvent.keyDown(moveButton(), { key: 'ArrowRight', shiftKey: true }); expect(onApply.mock.calls[0][0].panels[0].x).toBe(document.panels[0].x + 10);
  fireEvent.keyDown(screen.getByRole('button', { name: '调整示意格框 1 气泡 1大小' }), { key: 'ArrowDown' });
  expect(onApply.mock.calls[1][0].panels[0].bubbles[0].height).toBe(document.panels[0].bubbles[0].height + 1);
  fireEvent.keyDown(moveButton(), { key: 'ArrowRight', isComposing: true }); expect(onApply).toHaveBeenCalledTimes(2);
});
it.each(['revision', 'document', 'disabled', 'owner', 'unmount'])('retires pointer gestures on %s changes including retained handlers', reason => {
  const onApply = vi.fn(); let revision = 1, current = true;
  const props = { document, getRevision: () => revision, isCurrent: () => current, onApply, disabled: false };
  const view = render(<ComicGeometryEditor {...props} />); const b = moveButton();
  fireEvent.pointerDown(b, { button: 0, clientX: 10, clientY: 10 });
  const key = Object.keys(b).find(k => k.startsWith('__reactProps'))!;
  const retained = (b as unknown as Record<string, { onPointerUp: (e: unknown) => void }>)[key].onPointerUp;
  if (reason === 'revision') revision++;
  if (reason === 'owner') current = false;
  if (reason === 'document') view.rerender(<ComicGeometryEditor {...props} document={structuredClone(document)} />);
  if (reason === 'disabled') view.rerender(<ComicGeometryEditor {...props} disabled />);
  if (reason === 'unmount') view.unmount();
  act(() => retained({ pointerId: 1, clientX: 20, clientY: 20 })); expect(onApply).not.toHaveBeenCalled();
});

const groupDocument = () => ({ ...structuredClone(document), panels: [structuredClone(document.panels[0]), structuredClone(fixture.expectedPanel)] }) as ComicDocument;
const selectGroup = () => { fireEvent.click(screen.getByLabelText('整体移动格框 1')); fireEvent.click(screen.getByLabelText('整体移动格框 2')); };
const groupRight = () => screen.getByRole('button', { name: '所选格框右移' });
const retainedGroupMove = () => {
  const button = groupRight(), key = Object.keys(button).find(value => value.startsWith('__reactProps'))!;
  return (button as unknown as Record<string, { onClick: () => void }>)[key].onClick;
};
it('moves a selected group once per action and keeps selection for subsequent current edits', () => {
  const onApply = vi.fn(), props = { document: groupDocument(), getRevision, isCurrent, onApply, disabled: false };
  const view = render(<ComicGeometryEditor {...props} />); selectGroup();
  const retained = retainedGroupMove(); act(() => { retained(); retained(); }); expect(onApply).toHaveBeenCalledTimes(1);
  expect(onApply.mock.calls[0][0].panels.map((panel: ComicDocument['panels'][number]) => panel.x)).toEqual([26, 170]);
  view.rerender(<ComicGeometryEditor {...props} document={onApply.mock.calls[0][0]} />);
  expect((screen.getByLabelText('整体移动格框 1') as HTMLInputElement).checked).toBe(true);
  fireEvent.click(groupRight()); expect(onApply).toHaveBeenCalledTimes(2);
  expect(onApply.mock.calls[1][0].panels.map((panel: ComicDocument['panels'][number]) => panel.x)).toEqual([36, 180]);
});
it.each(['revision', 'document', 'disabled', 'owner', 'unmount', 'selection-ABA', 'step-ABA'])('rejects retired group callbacks after %s without losing valid current input', reason => {
  const onApply = vi.fn(); let revision = 1, current = true;
  const props = { document: groupDocument(), getRevision: () => revision, isCurrent: () => current, onApply, disabled: false };
  const view = render(<ComicGeometryEditor {...props} />); selectGroup(); const retained = retainedGroupMove();
  if (reason === 'revision') revision++;
  if (reason === 'owner') current = false;
  if (reason === 'document') view.rerender(<ComicGeometryEditor {...props} document={structuredClone(props.document)} />);
  if (reason === 'disabled') view.rerender(<ComicGeometryEditor {...props} disabled />);
  if (reason === 'unmount') view.unmount();
  if (reason === 'selection-ABA') { fireEvent.click(screen.getByLabelText('整体移动格框 1')); fireEvent.click(screen.getByLabelText('整体移动格框 1')); }
  if (reason === 'step-ABA') { fireEvent.change(screen.getByLabelText('整体平移步长'), { target: { value: '1' } }); fireEvent.change(screen.getByLabelText('整体平移步长'), { target: { value: '10' } }); }
  act(() => retained()); expect(onApply).not.toHaveBeenCalled();
  if (reason.endsWith('ABA')) { fireEvent.click(groupRight()); expect(onApply).toHaveBeenCalledTimes(1); }
});
