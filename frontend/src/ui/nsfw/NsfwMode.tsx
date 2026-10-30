// [HERMIA-FE-20261030 NSFW] 成人内容（NSFW）模式入口：设置菜单一项 + 18+ 确认对话框 + 顶栏状态标。仅界面偏好（见 nsfwMode.ts）。
import {useEffect, useMemo, useState} from 'react';
import {useStudio} from '../../store';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {useT} from '../../i18n';
import {ConfirmDialog} from '../ConfirmDialog';
import {disableNsfwMode, enableNsfwMode, useNsfwMode} from './nsfwMode';
import './nsfwMode.css';
import './nsfwTheme.css';

export type NsfwController = {on: boolean; session: boolean; asking: boolean; request: () => void; cancel: () => void; confirm: () => void; turnOff: () => void};

export function useNsfwController(): NsfwController {
  const actorId = useStudio(s => s.actor?.id), collab = useStudio(s => s.scope), novelId = useStudio(s => s.novelId);
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope: collab, projectId: novelId || null}), [actorId, collab, novelId]);
  const on = useNsfwMode(identity);
  useEffect(() => { // [NSFW-THEME] root attribute drives the token override; removed on off/unmount
    const el = document.documentElement;
    if (on) el.setAttribute('data-nsfw', 'on'); else el.removeAttribute('data-nsfw');
    return () => el.removeAttribute('data-nsfw');
  }, [on]);
  const [askedFor, setAskedFor] = useState<string | null>(null);
  const asking = askedFor === identity.key && !on; // a dialog opened for identity A never applies to B
  return {
    on, session: identity.kind !== 'real', asking,
    request: () => { if (!on) setAskedFor(identity.key); },
    cancel: () => setAskedFor(null),
    confirm: () => { if (askedFor === identity.key) enableNsfwMode(identity); setAskedFor(null); },
    turnOff: () => { setAskedFor(null); disableNsfwMode(identity); },
  };
}

/** Row inside the header 设置 menu. Off → opens the 18+ dialog; on → turns off immediately. */
export function NsfwMenuItem({c, onDone}: {c: NsfwController; onDone: () => void}) {
  const t = useT();
  return (
    <div className="nsfw-item" data-nsfw-setting={c.on ? 'on' : 'off'}>
      <button type="button" role="menuitemcheckbox" aria-checked={c.on} data-nsfw-toggle
        onClick={() => { onDone(); if (c.on) c.turnOff(); else c.request(); }}>
        <span>{t('nsfw.menu.label')}</span>
        <small className="nsfw-item__state" data-on={c.on}>{c.on ? t('nsfw.menu.on') : t('nsfw.menu.off')} · {c.on ? t('nsfw.menu.turnOff') : t('nsfw.menu.turnOn')}</small>
      </button>
      <p className="nsfw-item__note" data-nsfw-honest>{t('nsfw.honest')}</p>
      <p className="nsfw-item__note" data-nsfw-persist={c.session ? 'session' : 'saved'}>{c.session ? t('nsfw.session') : t('nsfw.saved')}</p>
    </div>
  );
}

export function NsfwConfirm({c}: {c: NsfwController}) {
  const t = useT();
  const [ack, setAck] = useState(false);
  if (!c.asking) return null;
  return (
    <ConfirmDialog title={t('nsfw.dialog.title')} confirmLabel={t('nsfw.dialog.confirm')} cancelLabel={t('nsfw.dialog.cancel')}
      tone="caution" initialFocus="cancel" confirmDisabled={!ack} testId="nsfw-dialog" confirmData={{'data-nsfw-confirm': ''}}
      onConfirm={() => { if (ack) c.confirm(); }} onCancel={() => { setAck(false); c.cancel(); }}>
      <ul>
        <li>{t('nsfw.dialog.age')}</li>
        <li>{t('nsfw.dialog.resp')}</li>
        <li>{t('nsfw.dialog.backend')}</li>
      </ul>
      <p data-nsfw-persist={c.session ? 'session' : 'saved'}>{c.session ? t('nsfw.session') : t('nsfw.saved')}</p>
      <label><input type="checkbox" data-nsfw-ack checked={ack} onChange={e => setAck(e.target.checked)} /> <span>{t('nsfw.dialog.ack')}</span></label>
    </ConfirmDialog>
  );
}

/** Header state tag, only while on. One click turns it off. */
export function NsfwBadge({c}: {c: NsfwController}) {
  const t = useT();
  if (!c.on) return null;
  return (
    <span className="nsfw-badge" data-nsfw-badge role="status" title={t('nsfw.badge.title')}>
      <span className="nsfw-badge__dot" aria-hidden="true" />
      <span className="nsfw-badge__label">{t('nsfw.badge')}</span>
      {c.session ? <span className="nsfw-badge__session">· {t('nsfw.badge.session')}</span> : null}
      <button type="button" className="nsfw-badge__off" aria-label={t('nsfw.badge.off')} data-nsfw-off onClick={c.turnOff}>{t('nsfw.badge.offShort')}</button>
    </span>
  );
}
