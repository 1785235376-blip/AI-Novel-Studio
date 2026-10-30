// [HERMIA-FE-20261030 B1] 通用确认对话框：role=dialog + aria-modal，打开时焦点进对话框，Tab/Shift+Tab 圈在内部，
// Esc = 取消，关闭（确认或取消）后焦点还给打开前的元素。颜色全部走主题 token。
import {useEffect, useId, useRef, type ReactNode} from 'react';
import './ConfirmDialog.css';

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function ConfirmDialog({title, children, confirmLabel, cancelLabel, onConfirm, onCancel, initialFocus = 'confirm', confirmDisabled = false, tone = 'default', testId, confirmData}: {
  title: string; children: ReactNode; confirmLabel: string; cancelLabel: string;
  onConfirm: () => void; onCancel: () => void;
  /** Which button gets focus on open. Risky actions should start on cancel. */
  initialFocus?: 'confirm' | 'cancel'; confirmDisabled?: boolean; tone?: 'default' | 'caution'; testId?: string;
  /** Extra data-* attributes for the confirm button (keeps existing selectors stable). */
  confirmData?: Record<`data-${string}`, string>;
}) {
  const box = useRef<HTMLDivElement>(null), ok = useRef<HTMLButtonElement>(null), no = useRef<HTMLButtonElement>(null);
  const returnTo = useRef<Element | null>(typeof document !== 'undefined' ? document.activeElement : null);
  const titleId = useId(), bodyId = useId();
  const cancelRef = useRef(onCancel); cancelRef.current = onCancel;
  useEffect(() => {
    const back = returnTo.current;
    (initialFocus === 'cancel' || confirmDisabled ? no : ok).current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cancelRef.current(); return; }
      if (e.key !== 'Tab' || !box.current) return;
      const items = [...box.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1], active = document.activeElement;
      if (e.shiftKey && (active === first || !box.current.contains(active))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (active === last || !box.current.contains(active))) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      if (back instanceof HTMLElement && back.isConnected) back.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- focus once on open
  }, []);
  return (
    <div className="cfd-backdrop" data-confirm-dialog-backdrop onMouseDown={e => { if (e.target === e.currentTarget) onCancel(); }}>
      <div ref={box} className="cfd" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={bodyId} data-tone={tone} data-testid={testId}>
        <h2 id={titleId} className="cfd__title">{title}</h2>
        <div id={bodyId} className="cfd__body">{children}</div>
        <div className="cfd__actions">
          <button ref={no} type="button" className="nv-btn" data-cfd-cancel onClick={onCancel}>{cancelLabel}</button>
          <button ref={ok} type="button" className="nv-btn nv-btn--primary" data-cfd-confirm {...confirmData} disabled={confirmDisabled} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
