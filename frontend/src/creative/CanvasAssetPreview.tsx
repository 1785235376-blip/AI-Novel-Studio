import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { AssetInspector } from '../novel/AssetInspector';
import { Button, StatusMessage } from '../ui/primitives';
import { apiErrorView } from '../api';
import type { StudioClient } from './studioClient';
import type { CanvasAssetReference } from './studioCanvasViewClient';
import { checkCanvasPreviewAsset, loadCanvasAssetPreview } from './canvasAssetPreviewHelpers';
type Props = { reference: CanvasAssetReference; owner: object; client: StudioClient; disabled: boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T> };
export function CanvasAssetPreview(props: Props) {
  const [result, setResult] = useState<{ token: object; value: Awaited<ReturnType<typeof loadCanvasAssetPreview>> }>(), [error, setError] = useState(''), [pending, setPending] = useState(false);
  const alive = useRef(true), inFlight = useRef(false), live = useRef(props); live.current = props;
  const values = [props.owner, props.client, props.disabled, JSON.stringify(props.reference)];
  const fence = useRef({ values, token: {} }); if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) fence.current = { values, token: {} };
  const token = fence.current.token;
  const current = useCallback(() => alive.current && fence.current.token === token && !live.current.disabled && live.current.isCurrent(), [token]);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => { setResult(undefined); setError(''); }, [token]);
  const visible = result?.token === token ? result.value : undefined;
  const download = useCallback(async () => {
    if (!visible || !current()) throw new Error('当前素材预览已过期。');
    await props.read(async () => { checkCanvasPreviewAsset(await props.client.asset(props.reference.asset_id), props.reference); if (!current()) throw new Error('当前素材选择已改变。'); });
    return visible.blob;
  }, [visible, current, props.client, props.read, props.reference]);
  async function load() {
    if (!current() || inFlight.current) return; inFlight.current = true; setPending(true); setError(''); setResult(undefined);
    try { const value = await props.read(() => loadCanvasAssetPreview(props.client, props.reference, current)); if (current()) setResult({ token, value }); }
    catch (reason) { if (current()) setError(apiErrorView(reason).message); }
    finally { inFlight.current = false; if (alive.current) setPending(false); }
  }
  return <section aria-label="所选画布素材预览"><Button disabled={props.disabled || pending} onClick={() => void load()}>核验并预览所选素材</Button><p>仅按需读取当前选中的一份素材，核对版本、大小和 SHA-256；单份上限 32 MiB，不批量加载画布媒体。</p>
    {pending && <StatusMessage>正在核对所选媒体内容…</StatusMessage>}{error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {visible && <AssetInspector asset={visible.asset} downloadAsset={download} isCurrent={current} showReferences={false} />}</section>;
}
