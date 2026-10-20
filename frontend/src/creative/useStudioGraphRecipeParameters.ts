import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import type { ProductionProvider } from './studioProductionClient';
import type { StudioGraphNode } from './studioGraphTypes';
import { checkedGraphRecipeParameters, graphRecipeParameterFields, graphRecipeParameterSupport, type GraphRecipeParameterFields } from './studioGraphRecipeParameters';

type Props = { identity: string; scope: object; revision: number; node?: StudioGraphNode; provider?: ProductionProvider; readable: boolean; editable: boolean;
  current: () => boolean; apply: (fields: GraphRecipeParameterFields, scope: object) => boolean };
type Form = { identity: string; owner: object; fields: GraphRecipeParameterFields; initial: GraphRecipeParameterFields; nodeId: string };

/** Session-only form. The original Graph command/Save/history/run remain the sole authorities. */
export function useStudioGraphRecipeParameters(props: Props) {
  const [form, setForm] = useState<Form>(), [error, setError] = useState('');
  const formRef = useRef(form), latest = useRef(props), alive = useRef(true);
  latest.current = props;
  const values = [props.identity, props.scope, props.revision, props.node, props.provider, props.readable, props.editable];
  const fence = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const owner = fence.current.token, reason = graphRecipeParameterSupport(props.node, props.provider);
  const live = () => alive.current && owner === fence.current.token && latest.current.readable && latest.current.editable
    && latest.current.current() && !graphRecipeParameterSupport(latest.current.node, latest.current.provider);
  const clear = useCallback(() => { formRef.current = undefined; setForm(undefined); setError(''); }, []);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; formRef.current = undefined; }; }, []);
  useLayoutEffect(() => { clear(); }, [props.identity, clear]);
  const visible = props.readable && form?.identity === props.identity ? form : undefined;
  const stale = !!visible && visible.owner !== owner;
  const fields = visible?.fields ?? (props.node ? graphRecipeParameterFields(props.node) : { steps: '', seed: '' });
  let validation = '';
  try { checkedGraphRecipeParameters(fields); } catch (e) { validation = e instanceof Error ? e.message : '采样参数不可用。'; }
  function edit(key: keyof GraphRecipeParameterFields, value: string) {
    if (!live() || stale || !latest.current.node || value.length > 32) return;
    const previous = formRef.current;
    if (previous && previous.owner !== owner) return;
    const initial = previous?.initial ?? graphRecipeParameterFields(latest.current.node);
    const next: Form = { identity: props.identity, owner, initial, nodeId: latest.current.node.id,
      fields: { ...(previous?.fields ?? initial), [key]: value } };
    formRef.current = next; setForm(next); setError('');
  }
  function apply() {
    if (!live() || !form || formRef.current !== form || form.owner !== owner || form.nodeId !== latest.current.node?.id) return;
    try {
      checkedGraphRecipeParameters(form.fields);
      if (!latest.current.apply({ ...form.fields }, props.scope)) throw new Error('原图、节点或写入权限已改变，采样参数未应用。');
      clear();
    } catch (e) { setError(e instanceof Error ? e.message : '采样参数未应用，原图保持不变。'); }
  }
  const pending = useCallback(() => !!formRef.current && JSON.stringify(formRef.current.fields) !== JSON.stringify(formRef.current.initial), []);
  return { reason, fields, stale, error: error || validation, formDirty: pending(), pending, clear, edit, apply,
    canEdit: props.readable && props.editable && !reason && !stale,
    canApply: props.readable && props.editable && !reason && !stale && !!form && pending() && !validation };
}
export type StudioGraphRecipeParameterState = ReturnType<typeof useStudioGraphRecipeParameters>;
