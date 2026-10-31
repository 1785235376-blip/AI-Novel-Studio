import { STUDIO_ENTRY_CONTRACT, STUDIO_INTERFACE_MODE_LABELS, STUDIO_INTERFACE_MODES, type StudioInterfaceMode } from './studioEntryTypes';
import { useTz } from '../i18n'; // [HERMIA-FE-20261031 VERA-P3 nav]
import './studioEntry.css';

/**
 * Presentation only. The workspace's own view-location owner persists the chosen mode;
 * this control is fully controlled and writes no storage. Switching changes nothing but
 * the rendering of the same project, assets, tasks and graph data.
 */
export function InterfaceModeSwitch({ mode, onChange }: { mode: StudioInterfaceMode; onChange: (mode: StudioInterfaceMode) => void }) {
  const z = useTz(); // [HERMIA-FE-20261031 VERA-P3 nav]
  return <section className="studio-entry-mode" aria-label={z('界面模式')}>
    <h3>{z('界面模式')}</h3>
    <div className="studio-entry-mode__options" role="radiogroup" aria-label={z('界面模式选择')}>
      {STUDIO_INTERFACE_MODES.map(option => <button
        key={option} type="button" role="radio" aria-checked={mode === option} disabled={mode === option}
        className={`studio-entry-mode__option${mode === option ? ' is-selected' : ''}`}
        onClick={() => { if (mode !== option) onChange(option); }}
      >{z(STUDIO_INTERFACE_MODE_LABELS[option])}</button>)}
    </div>
    <p className="studio-entry-mode__scope">{z(STUDIO_ENTRY_CONTRACT.notices.mode_scope)}</p>
  </section>;
}
