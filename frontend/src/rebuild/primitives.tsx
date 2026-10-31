// [HERMIA-FE-20261022 REBUILD-SHELL] Popover / Drawer / StateTag — prototype shell primitives.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './rebuild.css';
import { t } from '../i18n'; // [HERMIA-FE-20261025 I18N P1]

export function Popover({ label, count, children, testId }: { label: string; count?: number; children: (close: () => void) => ReactNode; testId?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const down = (ev: MouseEvent) => { if (ref.current && !ref.current.contains(ev.target as Node)) setOpen(false); };
    const key = (ev: KeyboardEvent) => { if (ev.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', down); document.addEventListener('keydown', key);
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key); };
  }, [open]);
  return <div className="rb-anchor" ref={ref} data-testid={testId}>
    <button type="button" className="rb-trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(v => !v)}>
      {label}{count ? <span className="rb-trigger__count">{count}</span> : null}
    </button>
    {open ? <div className="rb-pop" role="dialog" aria-label={label}>{children(() => setOpen(false))}</div> : null}
  </div>;
}

export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => { const key = (ev: KeyboardEvent) => { if (ev.key === 'Escape') onClose(); }; document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key); }, [onClose]);
  // Portal: header creates a stacking context; drawer must sit above the inspector.
  return createPortal(<aside className="rb-drawer" role="complementary" aria-label={title}>
    <header className="rb-drawer__head"><h2 className="rb-h">{title}</h2><button type="button" className="rb-btn" onClick={onClose} aria-label={t('pr.closeOf', { title })}>{t('pr.close')}</button></header>
    <div className="rb-drawer__body">{children}</div>
  </aside>, document.body);
}

export type Tone = 'ok' | 'warn' | 'err' | 'muted';
export function StateTag({ tone, children }: { tone: Tone; children: ReactNode }) { return <span className="rb-tag" data-tone={tone}>{children}</span>; }
export function Tabs<T extends string>({ value, items, onChange, label }: { value: T; items: { id: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return <div className="rb-tabs" role="tablist" aria-label={label}>{items.map(it => <button key={it.id} type="button" role="tab" aria-selected={value === it.id} onClick={() => onChange(it.id)}>{it.label}</button>)}</div>;
}
export function downloadText(filename: string, content: string, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
// [HERMIA-FE-20261022 REBUILD] Use the app QueryClient when mounted inside it; otherwise (isolated
// routes/tests) provide a private one so rebuild panels never crash their host.
import { QueryClient, QueryClientContext, QueryClientProvider } from '@tanstack/react-query';
import { useContext } from 'react';
let fallbackClient: QueryClient | null = null;
export function WithQuery({ children }: { children: ReactNode }) {
  const existing = useContext(QueryClientContext);
  if (existing) return <>{children}</>;
  fallbackClient ??= new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={fallbackClient}>{children}</QueryClientProvider>;
}
