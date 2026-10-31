import { checkedHandoffConfirm, handoffCanonical, type HandoffConfirm } from './studioComicHandoffClient';

const prefix = 'studio-comic-handoff-attempt/1:';
const failure = () => new Error('无法核对浏览器会话中的交接恢复标识。请保留原请求 ID，检查会话存储后重新打开。');
/** Bounded browser recovery intent only; never stores session tokens or PNGs. */
export function readComicHandoffAttempt(ownerKey: string): HandoffConfirm | undefined {
  try {
    const raw = sessionStorage.getItem(prefix + ownerKey);
    if (raw === null) return undefined;
    if (raw.length > 16000) throw failure();
    return checkedHandoffConfirm(JSON.parse(raw));
  } catch { throw failure(); }
}
export function saveComicHandoffAttempt(ownerKey: string, value: HandoffConfirm): void {
  const confirm = checkedHandoffConfirm(value), previous = readComicHandoffAttempt(ownerKey);
  if (previous && handoffCanonical(previous) !== handoffCanonical(confirm)) throw failure();
  const raw = JSON.stringify(confirm);
  if (raw.length > 16000) throw failure();
  try {
    sessionStorage.setItem(prefix + ownerKey, raw);
    if (sessionStorage.getItem(prefix + ownerKey) !== raw) throw failure();
  } catch { throw failure(); }
}
export function clearComicHandoffAttempt(ownerKey: string, requestId: string): void {
  if (readComicHandoffAttempt(ownerKey)?.request_id !== requestId) throw failure();
  try { sessionStorage.removeItem(prefix + ownerKey); if (sessionStorage.getItem(prefix + ownerKey) !== null) throw failure(); }
  catch { throw failure(); }
}
