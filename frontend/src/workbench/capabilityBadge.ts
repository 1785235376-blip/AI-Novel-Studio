/**
 * [HERMIA-FE-20261022 H-P1-02] Capability badge mapping — ban fake green.
 * `connected` / success tone ONLY when the ledger (or PanelDefinition) is explicitly connected.
 * `undetermined` → label「状态待核实」, tone never success.
 */
import type {CapabilityStatus} from './panels';

export type CapabilityBadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'error';

export interface CapabilityBadgeView {
  status: CapabilityStatus;
  label: string;
  tone: CapabilityBadgeTone;
  /** partial = editable draft semantics (honest, not "fully online"). */
  draftEditable: boolean;
}

/** Map PanelRegistry / workbench CapabilityStatus → author-facing badge. */
export function capabilityBadgeView(status: CapabilityStatus): CapabilityBadgeView {
  switch (status) {
    case 'connected':
      return {status, label: '已接通', tone: 'success', draftEditable: true};
    case 'partial':
      return {status, label: '部分可用 · 可编辑草稿', tone: 'warning', draftEditable: true};
    case 'local-only':
      return {status, label: '仅本机', tone: 'info', draftEditable: true};
    case 'not-implemented':
      return {status, label: '未实现', tone: 'neutral', draftEditable: false};
    case 'undetermined':
    default:
      return {status: 'undetermined', label: '状态待核实', tone: 'neutral', draftEditable: false};
  }
}

/**
 * Map static ledger cell text (HERMIA_CAPABILITY_LEDGER_*) → CapabilityStatus.
 * Never invents connected from vague PARTIAL / 无法判定 wording.
 */
export function capabilityFromLedgerCell(cell: string | null | undefined): CapabilityStatus {
  const t = (cell || '').trim();
  if (!t) return 'undetermined';
  if (/无法判定|undetermined|待核实|NOT_RUN/i.test(t)) return 'undetermined';
  if (/^connected$|已接通|真实接通/i.test(t) && !/partial|部分|未/i.test(t)) return 'connected';
  if (/PARTIAL|部分|草稿|仅前端|源码存在/i.test(t)) return 'partial';
  if (/local-only|仅本机|LOCAL_ONLY/i.test(t)) return 'local-only';
  if (/未实现|not-implemented|未定位|缺口/i.test(t)) return 'not-implemented';
  return 'undetermined';
}

/** Hard rule helper for tests / callers: undetermined must never look connected. */
export function isFakeGreen(status: CapabilityStatus, tone: CapabilityBadgeTone): boolean {
  return status !== 'connected' && tone === 'success';
}
