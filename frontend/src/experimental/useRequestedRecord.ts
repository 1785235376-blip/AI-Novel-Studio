import { useLayoutEffect, useRef } from 'react';

/** Focus a requested source only after its original owner has read it. */
export function useRequestedRecord(requestedId: string | undefined, rows: { id: string }[] | undefined,
  ready: boolean, identity: unknown) {
  const ref = useRef<HTMLElement>(null), focused = useRef<string>();
  const found = !!requestedId && ready && !!rows?.some(row => row.id === requestedId);
  useLayoutEffect(() => { focused.current = undefined; }, [identity, requestedId]);
  useLayoutEffect(() => {
    if (found && ref.current && focused.current !== requestedId) {
      focused.current = requestedId;
      ref.current.focus(); ref.current.scrollIntoView?.({ block: 'nearest' });
    }
  }, [found, requestedId, identity]);
  return { ref, found, missing: !!requestedId && ready && !found };
}
