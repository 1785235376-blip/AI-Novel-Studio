import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioClient, StudioReference } from './studioClient';

export type AssetReferencePin = Pick<StudioReference, 'kind' | 'id' | 'version' | 'digest'>;

/** Inspects a saved reference against the existing authorized directory. No history is invented. */
export function AssetReferenceInspection({ expected, client, read, isCurrent, busy, onOpenAsset }: {
  expected: AssetReferencePin;
  client: Pick<StudioClient, 'references'>;
  read: <T>(operation: () => Promise<T>) => Promise<T>;
  isCurrent: () => boolean;
  busy: boolean;
  onOpenAsset?: (pin: AssetReferencePin) => void;
}) {
  const [result, setResult] = useState<{ epoch: number; reference?: StudioReference; notice: string }>();
  const [pending, setPending] = useState(false);
  const receipt = useRef<typeof result>();
  const life = useRef({ client, pin: JSON.stringify(expected), busy, epoch: 0 });
  const pin = JSON.stringify(expected);
  if (life.current.client !== client || life.current.pin !== pin || life.current.busy !== busy) {
    life.current = { client, pin, busy, epoch: life.current.epoch + 1 };
  }
  const epoch = life.current.epoch;
  const alive = useRef(true), request = useRef<AbortController>();
  const valid = () => alive.current && life.current.epoch === epoch && isCurrent();
  useEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); }; }, []);
  useEffect(() => { request.current?.abort(); request.current = undefined; setPending(false); }, [epoch]);
  const shown = result?.epoch === epoch && isCurrent() ? result : undefined;
  const exact = shown?.reference && !shown.reference.deleted && shown.reference.version === expected.version && shown.reference.digest === expected.digest;
  async function inspect() {
    if (!valid() || busy || request.current) return;
    const abort = new AbortController(); request.current = abort;
    setPending(true); receipt.current = undefined; setResult(undefined);
    try {
      const data = await read(() => client.references(expected.kind, abort.signal));
      if (!valid() || abort.signal.aborted) return;
      const matches = data.items.filter(item => item.kind === expected.kind && item.id === expected.id);
      const reference = matches.length === 1 ? matches[0] : undefined;
      const next = { epoch, reference, notice: !reference || reference.deleted
        ? '来源缺失、已删除或当前不可读；未打开其他来源。'
        : reference.version === expected.version && reference.digest === expected.digest
          ? '当前可读来源与关联时的版本和摘要一致。打开前仍会再次读取原资产。'
          : '来源版本或摘要已变化；未改用最新版本。此入口没有历史正文读取契约。' };
      receipt.current = next; setResult(next);
    } catch {
      if (valid() && !abort.signal.aborted) setResult({ epoch, notice: '来源核对失败或当前无权读取，已清除上次核对结果。请重新核对。' });
    } finally {
      if (request.current === abort) { request.current = undefined; if (valid()) setPending(false); }
    }
  }
  return <section aria-label="关联版本核对">
    <p>关联时 {expected.kind} · {expected.id} · v{expected.version} · SHA-256 {expected.digest}</p>
    <Button variant="ghost" disabled={busy || pending} onClick={() => void inspect()}>核对原来源版本</Button>
    {pending && <StatusMessage>正在读取当前可访问的来源目录…</StatusMessage>}
    {shown && <><StatusMessage>{shown.notice}</StatusMessage>{shown.reference && <p>当前可读 {shown.reference.label} · v{shown.reference.version} · SHA-256 {shown.reference.digest}</p>}</>}
    {expected.kind !== 'ASSET' && <p>这里只核对章节／剧本元数据，不读取历史正文，也不改变原编辑器选择。</p>}
    {expected.kind === 'ASSET' && onOpenAsset && <Button disabled={busy || pending || !exact} onClick={() => {
      if (valid() && !busy && !request.current && exact && receipt.current === shown) onOpenAsset({ ...expected });
    }}>打开核对的原资产</Button>}
  </section>;
}
