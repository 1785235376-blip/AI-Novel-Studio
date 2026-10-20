import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import { ReceiptNavigation } from './ProductionReceiptReview';
import type { WorkspaceNavigation } from './uxClient';

type PristineReplayGate = { pristine: boolean; retire: () => void; consume: () => boolean };

/** Private authority-lifetime capability. Editing intent can retire it, never renew it. */
export function usePristineReplayNavigation(): PristineReplayGate {
  const live = useRef({ active: true, pristine: true });
  const [pristine, setPristine] = useState(true);
  const retire = useCallback(() => {
    if (!live.current.pristine) return;
    live.current.pristine = false;
    setPristine(false);
  }, []);
  const consume = useCallback(() => {
    if (!live.current.active || !live.current.pristine) return false;
    retire();
    return true;
  }, [retire]);
  useLayoutEffect(() => {
    live.current.active = true;
    return () => { live.current.active = false; };
  }, []);
  return useMemo(() => ({ pristine, retire, consume }), [pristine, retire, consume]);
}

/** Only the pristine primary replay action gets this capability. */
export function PristineReplayNavigation({ gate, target, receiptIdentity, onNavigate, disabled }: {
  gate: PristineReplayGate; target?: WorkspaceNavigation; receiptIdentity: string;
  onNavigate?: (target: WorkspaceNavigation) => void; disabled: boolean;
}) {
  const key = JSON.stringify([target, receiptIdentity, disabled, gate.pristine]);
  const live = useRef({ active: true, key, callback: onNavigate, consume: gate.consume, epoch: 0 });
  if (live.current.key !== key || live.current.callback !== onNavigate || live.current.consume !== gate.consume) {
    live.current = { active: true, key, callback: onNavigate, consume: gate.consume, epoch: live.current.epoch + 1 };
  }
  const epoch = live.current.epoch;
  useLayoutEffect(() => {
    live.current.active = true;
    return () => { live.current.active = false; };
  }, []);
  if (!gate.pristine) return <ReceiptNavigation target={target} label="审核重放产物" receiptIdentity={receiptIdentity} onNavigate={onNavigate} disabled={disabled} />;
  return <Button disabled={disabled || !target || !onNavigate} onClick={() => {
    if (!live.current.active || live.current.epoch !== epoch || disabled || !target || !onNavigate) return;
    // Check and consume synchronously: a retained handler cannot reuse pristine state.
    if (!gate.consume()) return;
    onNavigate(target);
  }}>审核重放产物</Button>;
}
