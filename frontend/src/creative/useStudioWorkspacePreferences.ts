import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioClient, StudioPreferences, StudioPreferencesInput } from './studioClient';
import { checkedStudioPreferences, preferenceInput, preferenceSaveFailure, samePreferenceInput } from './studioWorkspacePreferences';

export type StudioWorkspacePreferencesProps = {
  initial?: StudioPreferences; denied: boolean; canMutate: boolean; busy: boolean; externalDirty: boolean;
  client: Pick<StudioClient, 'preferences' | 'savePreferences'>; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onAdopt: (value: StudioPreferences) => void;
  isExternallyDirty?: () => boolean;
};

/** CAS, uncertain writes and draft adoption remain here when the form is restyled. */
export function useStudioWorkspacePreferences({ initial, denied, canMutate, busy, externalDirty, client, isCurrent, read, mutate, onAdopt, isExternallyDirty }: StudioWorkspacePreferencesProps) {
  const [base, setBase] = useState<StudioPreferences>(), [draft, setDraft] = useState<StudioPreferencesInput>();
  const [candidate, setCandidate] = useState<StudioPreferences>(), [confirmed, setConfirmed] = useState(false);
  const [failure, setFailure] = useState<'CONFLICT' | 'UNKNOWN'>(), [pending, setPending] = useState<'SAVE' | 'READ'>();
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const alive = useRef(true), epoch = useRef(0), inFlight = useRef(false);
  const reading = useRef<AbortController>();
  const baseRef = useRef(base); baseRef.current = base;
  const draftRef = useRef(draft); draftRef.current = draft;
  const current = useCallback(() => alive.current && !denied && isCurrent(), [denied, isCurrent]);
  const adopt = useCallback((value: StudioPreferences) => {
    baseRef.current = value; draftRef.current = preferenceInput(value);
    setBase(value); setDraft(draftRef.current); setCandidate(undefined); setConfirmed(false); setFailure(undefined); setError('');
    onAdopt(value);
  }, [onAdopt]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; reading.current?.abort(); }; }, []);
  useEffect(() => {
    if (denied) { epoch.current++; reading.current?.abort(); baseRef.current = undefined; draftRef.current = undefined; setBase(undefined); setDraft(undefined); setCandidate(undefined); setConfirmed(false); setFailure(undefined); setPending(undefined); setError(''); setNotice(''); }
    else if (initial && !baseRef.current && current()) {
      const value = checkedStudioPreferences(initial); baseRef.current = value; draftRef.current = preferenceInput(value); setBase(value); setDraft(draftRef.current);
    }
  }, [initial, denied, current]);
  const dirty = !!base && !!draft && !samePreferenceInput(base, draft);
  const blocked = !!failure;
  const editable = !!base && !!draft && canMutate && !denied && !busy && !externalDirty && !pending && !blocked;
  const externallyBlocked = () => externalDirty || !!isExternallyDirty?.();
  const canCheck = !!base && !denied && !busy && !externalDirty && !pending;
  const canAdopt = !!candidate && confirmed && canCheck;
  const change = (value: StudioPreferencesInput) => {
    if (!editable || !current() || inFlight.current || externallyBlocked()) return;
    draftRef.current = preferenceInput(value); setDraft(draftRef.current); setCandidate(undefined); setConfirmed(false); setError(''); setNotice('');
  };
  async function save() {
    const source = baseRef.current, input = draftRef.current;
    if (!source || !input || !editable || !dirty || inFlight.current || !current() || externallyBlocked()) return;
    const request = ++epoch.current, snapshot = preferenceInput(input);
    inFlight.current = true; setPending('SAVE'); setCandidate(undefined); setConfirmed(false); setError(''); setNotice('');
    try {
      const saved = checkedStudioPreferences(await mutate(() => client.savePreferences(snapshot, source.version)));
      if (saved.version !== source.version + 1 || !samePreferenceInput(saved, snapshot)) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '保存回执与提交版本或内容不一致，请读取服务端核对。' });
      if (current() && epoch.current === request) { adopt(saved); setNotice('创作偏好已保存。模块和权限保持原行为。'); }
    } catch (reason) {
      if (current() && epoch.current === request) {
        const kind = preferenceSaveFailure(reason); setFailure(kind === 'REJECTED' ? undefined : kind);
        setError(apiErrorView(reason, '偏好未确认保存，当前输入已保留。').message);
      }
    } finally { inFlight.current = false; if (current() && epoch.current === request) setPending(undefined); }
  }
  async function checkServer() {
    if (!baseRef.current || busy || externallyBlocked() || inFlight.current || !current()) return;
    const request = ++epoch.current, abort = new AbortController();
    reading.current = abort;
    inFlight.current = true; setPending('READ'); setCandidate(undefined); setConfirmed(false); setError('');
    try {
      // Use the workspace's activity lock even for this explicit read: it must
      // not be interleaved with leaving, saving a graph, or a model action.
      const value = checkedStudioPreferences(await mutate(() => read(() => client.preferences(abort.signal))));
      if (value.version < baseRef.current!.version) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务端偏好版本早于当前已读取版本，请重新核对。' });
      if (current() && epoch.current === request) {
        setCandidate(value);
        setNotice('已读取服务端当前版本。核对后明确选择采用服务端值，或保留输入并以此版本继续编辑；不会自动覆盖或再次保存。');
      }
    } catch (reason) { if (current() && epoch.current === request) setError(apiErrorView(reason, '服务端偏好读取失败，输入与待核对状态仍保留。').message); }
    finally { if (reading.current === abort) reading.current = undefined; inFlight.current = false; if (current() && epoch.current === request) setPending(undefined); }
  }
  function adoptCandidate(keepDraft: boolean) {
    if (!candidate || !confirmed || busy || externallyBlocked() || inFlight.current || !current() || keepDraft && !canMutate) return;
    const input = draftRef.current;
    adopt(candidate);
    if (keepDraft && input) { draftRef.current = preferenceInput(input); setDraft(draftRef.current); }
    setNotice(keepDraft ? '服务端版本已核对，本地输入仍保留。需要你再次明确保存。' : '已采用读取的服务端偏好；没有再次保存。');
  }
  const discard = () => {
    if (inFlight.current || !current()) return;
    if (baseRef.current) { draftRef.current = preferenceInput(baseRef.current); setDraft(draftRef.current); }
    setCandidate(undefined); setConfirmed(false);
    // Leaving/discarding input never proves an uncertain write failed.
  };
  return { base, draft, candidate, confirmed, failure, pending, error, notice, dirty, blocked, editable, canCheck, canAdopt, canKeepDraft: canAdopt && canMutate, change, save, checkServer, adoptCandidate, discard, setConfirmed };
}
export type StudioWorkspacePreferencesController = ReturnType<typeof useStudioWorkspacePreferences>;
