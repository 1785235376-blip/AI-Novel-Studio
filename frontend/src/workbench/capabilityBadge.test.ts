/**
 * [HERMIA-FE-20261022 H-P1-02] Ban fake green — undetermined never success/connected.
 */
import {describe, expect, it} from 'vitest';
import {
  capabilityBadgeView,
  capabilityFromLedgerCell,
  isFakeGreen,
} from './capabilityBadge';
import type {CapabilityStatus} from './panels';

describe('capabilityBadgeView', () => {
  const all: CapabilityStatus[] = ['connected', 'partial', 'local-only', 'not-implemented', 'undetermined'];
  it('maps every status with honest labels', () => {
    expect(capabilityBadgeView('connected')).toMatchObject({label: '已接通', tone: 'success'});
    expect(capabilityBadgeView('partial')).toMatchObject({label: '部分可用 · 可编辑草稿', tone: 'warning', draftEditable: true});
    expect(capabilityBadgeView('local-only').tone).toBe('info');
    expect(capabilityBadgeView('not-implemented').label).toBe('未实现');
    expect(capabilityBadgeView('undetermined')).toMatchObject({label: '状态待核实', tone: 'neutral'});
  });
  it('never paints undetermined / partial / local-only / not-implemented as success (fake green)', () => {
    for (const status of all) {
      const view = capabilityBadgeView(status);
      expect(isFakeGreen(view.status, view.tone)).toBe(false);
      if (status !== 'connected') expect(view.tone).not.toBe('success');
    }
  });
});

describe('capabilityFromLedgerCell', () => {
  it('maps PARTIAL / 无法判定 without inventing connected', () => {
    expect(capabilityFromLedgerCell('PARTIAL（后端+前端源码存在）')).toBe('partial');
    expect(capabilityFromLedgerCell('无法判定（252e88fe 未定位）')).toBe('undetermined');
    expect(capabilityFromLedgerCell('已接通')).toBe('connected');
    expect(capabilityFromLedgerCell('')).toBe('undetermined');
    expect(capabilityFromLedgerCell('未实现')).toBe('not-implemented');
  });
  it('refuses to treat vague PARTIAL wording as connected', () => {
    const status = capabilityFromLedgerCell('PARTIAL（仅前端源码定位）');
    const view = capabilityBadgeView(status);
    expect(status).toBe('partial');
    expect(view.tone).not.toBe('success');
    expect(view.label).toContain('部分可用');
  });
});
