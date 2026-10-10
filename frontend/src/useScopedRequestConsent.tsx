import {useEffect, useRef, useState} from 'react';
import {useStudio} from './store';
import {ApiError} from './api';

function scopeIdentity(state: ReturnType<typeof useStudio.getState>) {
  return JSON.stringify([state.sessionToken, state.actor?.id, state.actor?.workspaceId,
    state.scope?.workspaceId, state.scope?.projectId, state.scope?.storylineId,
    state.scope?.branchId, state.novelId]);
}

/** Per-request consent is memory-only and never survives edits or identity changes. */
export function useScopedRequestConsent(inputs: unknown[]) {
  const scopeKey = useStudio(scopeIdentity);
  const key = JSON.stringify([scopeKey, ...inputs]);
  const live = useRef({key, revision: 0, sequence: 0, scopeEpoch: 0, mounted: false});
  if (live.current.key !== key) {
    live.current.key = key;
    live.current.revision += 1;
    live.current.sequence += 1;
  }
  const [approvedRevision, setApprovedRevision] = useState<number | null>(null);
  useEffect(() => {
    live.current.mounted = true;
    let observed=scopeIdentity(useStudio.getState());
    const unsubscribe=useStudio.subscribe(state=>{const next=scopeIdentity(state);if(next!==observed){observed=next;live.current.revision+=1;live.current.sequence+=1;live.current.scopeEpoch+=1;setApprovedRevision(null);}});
    return () => {unsubscribe();live.current.mounted = false; live.current.sequence += 1;};
  }, []);
  const begin = () => {
    const revision = live.current.revision, sequence = ++live.current.sequence, scope = scopeKey;
    setApprovedRevision(null);
    return () => live.current.mounted && live.current.revision === revision &&
      live.current.sequence === sequence && scopeIdentity(useStudio.getState()) === scope;
  };
  return {
    scopeKey, requestKey: key, get allowed() {return approvedRevision === live.current.revision;},
    setAllowed: (value: boolean) => setApprovedRevision(value ? live.current.revision : null),
    begin,
    captureScope: () => {const scope=scopeKey,epoch=live.current.scopeEpoch; return () => live.current.mounted && live.current.scopeEpoch === epoch && scopeIdentity(useStudio.getState()) === scope;},
  };
}

export function CloudPromptConsent({target, checked, onChange, automatic = false, preferences = false}: {
  target: string; checked: boolean; onChange: (value: boolean) => void; automatic?: boolean; preferences?: boolean;
}) {
  return <div>
    <label><input type="checkbox" checked={checked && !automatic} disabled={automatic} onChange={event => onChange(event.target.checked)}/>
      允许本次向 {target || '所选云端 Provider'} 发送手工输入的提示词/文本及选定参考资料{preferences ? '，以及已允许共享的偏好' : ''}
    </label>
    <p className="novel-help">本地调用无需勾选。{automatic ? '自动选择时不授权云端发送；如需云端，请先选择具体 Provider。' : '修改模型、输入或参考资料后需重新确认。'}章节和项目的隐私限制仍单独执行，勾选不会解除限制。</p>
  </div>;
}

export function cloudPromptReviewMessage(error: unknown, fallback: string) {
  return error instanceof ApiError && error.problem.code === 'CLOUD_PROMPT_REVIEW_REQUIRED'
    ? '云端尚未获准接收本次输入，或主机未启用云端。请确认本次授权或选择本地模型。'
    : fallback;
}
