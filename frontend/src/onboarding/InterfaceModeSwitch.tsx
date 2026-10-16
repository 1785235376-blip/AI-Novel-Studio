import { STUDIO_ENTRY_CONTRACT, STUDIO_INTERFACE_MODE_LABELS, STUDIO_INTERFACE_MODES, type StudioInterfaceMode } from './studioEntryTypes';
import './studioEntry.css';

/**
 * Presentation only. The workspace's own view-location owner persists the chosen mode;
 * this control is fully controlled and writes no storage. Switching changes nothing but
 * the rendering of the same project, assets, tasks and graph data.
 */
export function InterfaceModeSwitch({ mode, onChange }: { mode: StudioInterfaceMode; onChange: (mode: StudioInterfaceMode) => void }) {
  return <section className="studio-entry-mode" aria-label="界面模式">
    <h3>界面模式</h3>
    <div className="studio-entry-mode__options" role="radiogroup" aria-label="界面模式选择">
      {STUDIO_INTERFACE_MODES.map(option => <button
        key={option} type="button" role="radio" aria-checked={mode === option} disabled={mode === option}
        className={`studio-entry-mode__option${mode === option ? ' is-selected' : ''}`}
        onClick={() => { if (mode !== option) onChange(option); }}
      >{STUDIO_INTERFACE_MODE_LABELS[option]}</button>)}
    </div>
    <p className="studio-entry-mode__scope">{STUDIO_ENTRY_CONTRACT.notices.mode_scope}</p>
  </section>;
}
