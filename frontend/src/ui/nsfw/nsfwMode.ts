/**
 * [HERMIA-FE-20261030 NSFW] 成人内容（NSFW）模式 —— 仅界面偏好。
 * 后端现状（8ea45399，只读核对）：app/creative/content_policy.py 是 RESERVED 预留，`WorkspacePreferences.content_policy`
 * 可存 STANDARD/MATURE/RESTRICTED/CUSTOM，但任何生成 / 模型 / 导出路径都不读它（STATUS="RESERVED"，模块注释明写“no UI switch”）。
 * 所以这里不写后端、不改任何请求，只在本机记住用户的界面选择，并在界面上如实标注「仅界面偏好，后端未接入」。
 * - 默认关；只有 enableNsfwMode()（由确认对话框调用）能打开；关闭随时一步完成。
 * - 有真实身份（账号 + 完整项目范围）⇒ 按 用户/项目/实例 存在本机 localStorage；否则「仅本次会话」，只放内存、零存储写入。
 * - 损坏 / 未知版本的存储值一律当作「关」，并且不改写它。
 */
import {useSyncExternalStore} from 'react';
import type {WorkspaceIdentity} from '../../workspace/contracts';

type St = {getItem(k: string): string | null; setItem(k: string, v: string): void; removeItem(k: string): void};
export const NSFW_KEY_PREFIX = 'poemseed.nsfwmode.v1';
const enc = encodeURIComponent;
const session = new Map<string, boolean>();
const listeners = new Set<() => void>();
let version = 0;
const emit = () => { version++; listeners.forEach(l => l()); };

export function nsfwStorageKey(id: Extract<WorkspaceIdentity, {kind: 'real'}>) {
  return `${NSFW_KEY_PREFIX}::${enc(id.scope.userId)}::${enc(id.scope.projectId)}::${enc(id.scope.projectInstanceId)}`;
}
const storage = (): St | null => { try { return globalThis.localStorage ?? null; } catch { return null; } };

export function readNsfwMode(id: WorkspaceIdentity, st: St | null = storage()): boolean {
  if (session.has(id.key)) return session.get(id.key)!;
  if (id.kind !== 'real' || !st) return false;
  try {
    const raw = st.getItem(nsfwStorageKey(id));
    if (raw == null) return false;
    const d = JSON.parse(raw) as {v?: unknown; on?: unknown};
    return d?.v === 1 && d.on === true;
  } catch { return false; }
}

export type NsfwWrite = 'saved' | 'session' | 'write-failed';
/** Only call from the explicit, confirmed 18+ dialog. */
export function enableNsfwMode(id: WorkspaceIdentity, st: St | null = storage()): NsfwWrite {
  session.set(id.key, true); emit();
  if (id.kind !== 'real' || !st) return 'session';
  try { st.setItem(nsfwStorageKey(id), JSON.stringify({v: 1, on: true})); return 'saved'; } catch { return 'write-failed'; }
}
export function disableNsfwMode(id: WorkspaceIdentity, st: St | null = storage()): NsfwWrite {
  session.set(id.key, false); emit();
  if (id.kind !== 'real' || !st) return 'session';
  try { st.removeItem(nsfwStorageKey(id)); return 'saved'; } catch { return 'write-failed'; }
}
export function useNsfwMode(id: WorkspaceIdentity): boolean {
  useSyncExternalStore(cb => { listeners.add(cb); return () => listeners.delete(cb); }, () => version, () => version);
  return readNsfwMode(id);
}
/** test-only */
export function __resetNsfwSession() { session.clear(); emit(); }
