/** Reuse visible saved content; never copy family identity, approval or bindings. */
import { useEffect, useRef } from 'react';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { Button } from '../ui/primitives';
import { useTz } from '../i18n'; // [HERMIA-FE-20261031 VERA-EN]
import { emptyContent, type Draft, type DraftContent } from './promptDraft';
import type { PromptEntry } from './promptTypes';

export function independentPromptContent(draft: Draft, detail: PromptEntry | null): DraftContent | null {
  if (!detail || !['CLEAN', 'SAVED'].includes(draft.state) || draft.pending || draft.requestId
      || !detail.readComplete || !detail.historyComplete || detail.redacted
      || detail.body.state !== 'COMPLETE' || detail.body.truncated || !detail.body.decodable
      || !detail.body.digest || !/^[a-f0-9]{64}$/.test(detail.body.digest)
      || draft.familyId !== detail.familyId || draft.baseAssetId !== detail.headAssetId
      || draft.baseRevision !== detail.revision || draft.content.text !== detail.body.value) return null;
  const c = draft.content;
  return { ...emptyContent(), text: c.text, negativePrompt: c.negativePrompt, purpose: c.purpose,
    modelReference: c.modelReference, parameters: c.parameters, seed: c.seed };
}

type Props = {
  draft: Draft; detail: PromptEntry | null; scopeKey: string; transport: StudioGraphTransport;
  disabled: boolean; onCopy: (content: DraftContent) => void;
};
export function PromptIndependentDraft(props: Props) {
  const z = useTz();
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const lifetime = useRef({ draft: props.draft, detail: props.detail, scopeKey: props.scopeKey,
    transport: props.transport, disabled: props.disabled, consumed: false });
  const retiredDetails = useRef(new WeakSet<PromptEntry>());
  const old = lifetime.current;
  if (old.scopeKey !== props.scopeKey && old.detail) retiredDetails.current.add(old.detail);
  if (old.draft !== props.draft || old.detail !== props.detail || old.scopeKey !== props.scopeKey
      || old.transport !== props.transport || old.disabled !== props.disabled) {
    lifetime.current = { draft: props.draft, detail: props.detail, scopeKey: props.scopeKey,
      transport: props.transport, disabled: props.disabled, consumed: false };
  }
  const captured = lifetime.current;
  const retired = !!props.detail && retiredDetails.current.has(props.detail);
  const content = retired ? null : independentPromptContent(props.draft, props.detail);
  return <section aria-label={z('独立复用 Prompt')}>
    <Button disabled={props.disabled || !content} onClick={() => {
      if (!alive.current || lifetime.current !== captured || captured.consumed || captured.disabled
          || (captured.detail && retiredDetails.current.has(captured.detail))) return;
      const fresh = independentPromptContent(captured.draft, captured.detail);
      if (!fresh) return;
      captured.consumed = true;
      props.onCopy(fresh);
    }}>{z('复制已载入版本为新草稿')}</Button>
    <p>{z('仅复用已载入的完整正文和生成参数。角色、场景、镜头、参考资产绑定及审核状态不会继承。 先保存当前修改，再复制；新草稿需另行保存，不会修改原 Prompt。')}</p>
  </section>;
}
