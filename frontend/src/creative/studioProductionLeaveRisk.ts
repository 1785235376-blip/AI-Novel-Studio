import { createContext, useContext, useLayoutEffect, useRef } from 'react';

// Only the original controller's request identity crosses this read-only boundary.
// Captured transports, credentials, drafts and source payloads never enter it.
export type StudioProductionLeaveRequest = { requestId: string; owner: string; operationId: string };
export type StudioProductionLeaveRisk = { unknown: boolean; requests: StudioProductionLeaveRequest[] };
export type StudioProductionLeaveGuard = {
  register: (read: () => StudioProductionLeaveRisk) => () => void;
  capture: () => void;
};
export const StudioProductionLeaveContext = createContext<StudioProductionLeaveGuard | undefined>(undefined);
export function useStudioProductionLeaveRisk(guard: StudioProductionLeaveGuard | undefined, read: () => StudioProductionLeaveRisk) {
  const inherited = useContext(StudioProductionLeaveContext), boundary = guard ?? inherited;
  const latest = useRef(read); latest.current = read;
  useLayoutEffect(() => boundary?.register(() => latest.current()), [boundary]);
  return boundary;
}
