import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { verifyCanvasGraphAsset, type CanvasGraphAssetHandoff } from './mediaCanvasGraphHandoffHelpers';
import type { CanvasAssetReference } from './studioCanvasViewClient';
import type { StudioClient } from './studioClient';
type Props = { reference: CanvasAssetReference; owner: object; disabled: boolean; isCurrent: () => boolean;
  client: Pick<StudioClient, 'asset'>; read: <T>(work: () => Promise<T>) => Promise<T>; handoff?: CanvasGraphAssetHandoff };
export function MediaCanvasGraphHandoff(props: Props) {
  const [verified, setVerified] = useState<{ token: object; scope: object; reference: CanvasAssetReference }>(), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const verifiedLive = useRef(verified); verifiedLive.current = verified;
  const [consent, setConsent] = useState(false), [notice, setNotice] = useState('');
  const alive = useRef(true), running = useRef(false), ticket = useRef(0), live = useRef(props); live.current = props;
  const values = [props.owner, props.client, JSON.stringify(props.reference), props.handoff?.scope, props.disabled];
  const fence = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const token = fence.current.token;
  const current = () => alive.current && fence.current.token === token && !live.current.disabled && live.current.isCurrent() && !!live.current.handoff?.isCurrent();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; ticket.current++; }; }, []);
  useLayoutEffect(() => { ticket.current++; setVerified(undefined); setConsent(false); setError(''); }, [token]);
  async function inspect() {
    if (!current() || running.current || !props.handoff?.available) return;
    const request = ++ticket.current, reference = { ...props.reference }, scope = props.handoff.scope;
    running.current = true; setBusy(true); verifiedLive.current = undefined; setVerified(undefined); setConsent(false); setError(''); setNotice('');
    try { const asset = await props.read(() => props.client.asset(reference.asset_id));
      if (!current() || request !== ticket.current || live.current.handoff?.scope !== scope) return;
      setVerified({ token, scope, reference: verifyCanvasGraphAsset(asset, reference) });
    } catch { if (current()) setError('当前素材引用未通过核对，未改动画布或执行图。'); }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }
  const candidate = verified?.token === token ? verified : undefined;
  function apply() {
    if (!current() || running.current || !candidate || verifiedLive.current !== candidate || !consent || !live.current.handoff?.available) return;
    verifiedLive.current = undefined; setConsent(false); setVerified(undefined); ticket.current++;
    if (live.current.handoff.insert(candidate.reference, candidate.scope)) setNotice('已加入执行图草稿；请在原图保存、连接与审核，不会自动运行。');
    else setError('目标图状态已变化，未加入引用。请重新核对。');
  }
  return <section aria-label="素材画布到执行图"><h4>加入当前执行图</h4><p>先保存素材画布，再把所选卡片作为原素材引用加入媒体、图片或视频图。只核对元数据；原保存和执行阶段仍会核对来源。不会复制文件、自动连线或运行模型。</p>
    <Button disabled={props.disabled || busy || !props.handoff?.available} onClick={() => void inspect()}>核对素材与目标图</Button>
    {candidate && <><p>{candidate.reference.asset_id} · v{candidate.reference.version} · {candidate.reference.kind}</p><label><input type="checkbox" checked={consent} disabled={busy || props.disabled} onChange={event => { if (current() && verifiedLive.current === candidate) setConsent(event.target.checked); }} />确认只加入当前执行图草稿</label><Button disabled={!consent || busy || props.disabled || !props.handoff?.available} onClick={apply}>加入素材引用节点</Button></>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
  </section>;
}
