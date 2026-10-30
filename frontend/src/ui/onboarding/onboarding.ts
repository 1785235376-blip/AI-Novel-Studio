/**
 * [HERMIA-UX-20261030 ONBOARD] 首次引导 —— 是否「已看过」的记录。
 * - 有真实身份（账号 + 完整项目范围）⇒ 按账号记在本机 localStorage（同一个人换项目不再重复弹）。
 * - 否则「仅本次会话」：只放内存，零存储写入。
 * - 损坏 / 未知版本的值当作「没看过」，但不改写它（与 NSFW 规则一致）。
 * 只是界面偏好：不写后端、不发请求、不调模型。
 */
import {useSyncExternalStore} from 'react';
import type {WorkspaceIdentity} from '../../workspace/contracts';

type St = {getItem(k: string): string | null; setItem(k: string, v: string): void};
export const ONBOARDING_KEY_PREFIX = 'poemseed.onboarding.v1';
const session = new Set<string>();
const listeners = new Set<() => void>();
let version = 0;
let openRequests = 0;
const emit = () => { version++; listeners.forEach(l => l()); };
const storage = (): St | null => { try { return globalThis.localStorage ?? null; } catch { return null; } };

export function onboardingStorageKey(id: Extract<WorkspaceIdentity, {kind: 'real'}>) {
  return `${ONBOARDING_KEY_PREFIX}::${encodeURIComponent(id.scope.userId)}`;
}
const sessionKey = (id: WorkspaceIdentity) => (id.kind === 'real' ? onboardingStorageKey(id) : id.key);

export function readOnboardingSeen(id: WorkspaceIdentity, st: St | null = storage()): boolean {
  if (session.has(sessionKey(id))) return true;
  if (id.kind !== 'real' || !st) return false;
  try {
    const raw = st.getItem(onboardingStorageKey(id));
    if (raw == null) return false;
    const d = JSON.parse(raw) as {v?: unknown; seen?: unknown};
    return d?.v === 1 && d.seen === true;
  } catch { return false; }
}

export type OnboardingWrite = 'saved' | 'session' | 'write-failed';
export function markOnboardingSeen(id: WorkspaceIdentity, st: St | null = storage()): OnboardingWrite {
  session.add(sessionKey(id)); emit();
  if (id.kind !== 'real' || !st) return 'session';
  try { st.setItem(onboardingStorageKey(id), JSON.stringify({v: 1, seen: true})); return 'saved'; } catch { return 'write-failed'; }
}

/** 设置菜单「重新查看引导」：只是请求再开一次，不清除「已看过」。 */
export function requestOnboarding() { openRequests++; emit(); }
export function useOnboardingStore(id: WorkspaceIdentity): {seen: boolean; requests: number} {
  useSyncExternalStore(cb => { listeners.add(cb); return () => listeners.delete(cb); }, () => version, () => version);
  return {seen: readOnboardingSeen(id), requests: openRequests};
}

/** 起步卡（「你想从哪里开始？」）关掉时广播，引导在它之后才出现，不叠在一起。 */
export const START_GATE_CLOSED_EVENT = 'studio:start-gate-closed';

/** test-only */
export function __resetOnboarding() { session.clear(); openRequests = 0; emit(); }
