// R3-I — read-only Prompt adoption panel for the currently selected Shot.
//
// It shows which Prompt revision is pinned to this shot, with the server's own provenance and
// source state. It contains NO write affordance: the production adoption switch is still closed,
// and a client must not imply otherwise. `403` is never interpreted here as "nothing was
// written" - this panel does not make commit claims at all.
import { useEffect, useRef, useState } from 'react';

import { Panel } from '../ui/primitives';
import { createPromptAdoptionClient, type AdoptionSource } from './promptAdoptionClient';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

export function PromptAdoptionPanel({ projectId, documentId, shotId, transport, enabled = true }: {
  projectId: string;
  documentId: string | null;
  shotId: string | null;
  transport: StudioGraphTransport;
  enabled?: boolean;
}) {
  const [source, setSource] = useState<AdoptionSource | null>(null);
  const [state, setState] = useState<'IDLE' | 'LOADING' | 'READY' | 'ERROR'>('IDLE');
  const [error, setError] = useState<string | null>(null);
  // Every read carries the identity it was issued for. A late response for a previous
  // project/document/shot must never overwrite the current selection.
  const epoch = useRef(0);
  const identity = `${projectId}\u0000${documentId ?? ''}\u0000${shotId ?? ''}`;

  useEffect(() => {
    if (!enabled || !documentId || !shotId) {
      setSource(null);
      setState('IDLE');
      setError(null);
      return;
    }
    const mine = ++epoch.current;
    const controller = new AbortController();
    setState('LOADING');
    setError(null);
    const client = createPromptAdoptionClient(projectId, transport);
    void client.forShot(documentId, shotId, controller.signal)
      .then(found => {
        if (mine !== epoch.current) return;   // a newer selection owns the panel now
        setSource(found);
        setState('READY');
      })
      .catch((reason: unknown) => {
        if (mine !== epoch.current) return;
        // A revocation or a permission failure must clear the previously shown private
        // provenance rather than leave it on screen.
        setSource(null);
        setState('ERROR');
        setError(reason instanceof Error ? reason.message : '无法读取采用记录。');
      });
    return () => { controller.abort(); };
  }, [identity, enabled, projectId, documentId, shotId, transport]);

  return (
    <Panel title="Prompt 采用来源">
      {state === 'IDLE' && (
        <p className="prompt-adoption-empty">选择一个镜头后可查看它的 Prompt 采用来源。</p>
      )}
      {state === 'LOADING' && <p className="prompt-adoption-loading">正在读取采用记录…</p>}
      {state === 'ERROR' && (
        <p className="prompt-adoption-error" role="alert">{error ?? '无法读取采用记录。'}</p>
      )}
      {state === 'READY' && !source && (
        <p className="prompt-adoption-empty">此镜头尚未采用任何 Prompt 修订。</p>
      )}
      {state === 'READY' && source && (
        <dl className="prompt-adoption-record">
          <dt>来源家族</dt><dd>{source.familyId}</dd>
          <dt>来源修订</dt><dd>{source.assetId} · r{source.revision}</dd>
          <dt>原始摘要</dt><dd className="prompt-adoption-digest">{source.digest}</dd>
          <dt>采用者</dt><dd>{source.adoptedBy || '未知'}</dd>
          <dt>采用时间</dt><dd>{source.adoptedAt || '未知'}</dd>
          <dt>采用结果版本</dt><dd>{source.resultVersion ?? '未知'}</dd>
          <dt>当前是否仍然生效</dt>
          <dd className={source.stillApplied ? 'is-applied' : 'is-stale'}>
            {source.stillApplied ? '仍然生效' : '已失效（镜头内容已被修改）'}
          </dd>
          <dt>来源是否可展示</dt>
          <dd className={source.sourceReadable ? 'is-readable' : 'is-masked'}>
            {source.sourceReadable
              ? '可展示'
              : source.sourceRedacted ? '来源已被遮罩' : '来源当前不可读'}
          </dd>
          <dt>是否存在更新版本</dt>
          <dd>{source.newerRevisionAvailable ? '存在更新版本，需要重新采用' : '无更新版本'}</dd>
        </dl>
      )}
    </Panel>
  );
}
