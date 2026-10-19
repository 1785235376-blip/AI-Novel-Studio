import { useLayoutEffect, useRef, useState } from 'react';
import { apiErrorView } from '../api';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';
import { buildLocalSubgraphParent, inspectLocalSubgraphSource, localSubgraphPinKey, type LocalSubgraphSource } from './graphLocalSubgraph';

type Props = { client: StudioGraphClient; identity: string; scope: object; readable: boolean; blank: boolean;
  current: () => boolean; locked: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>;
  onRecords: (records: StudioGraphRecord[]) => void; onCatalog: (catalog: StudioGraphCatalog) => void;
  apply: (definition: StudioGraphDefinition, catalog: StudioGraphCatalog, scope: object) => boolean };

/** Session-local reviewed source selection; original change/Save/run own every write. */
export function useGraphLocalSubgraphParent(props: Props) {
  const [rows, setRows] = useState<StudioGraphRecord[]>([]), [catalog, setCatalog] = useState<StudioGraphCatalog>();
  const [choice, setChoice] = useState(''), [text, setText] = useState(''), [preview, setPreview] = useState<LocalSubgraphSource>();
  const [consent, setConsent] = useState(''), [error, setError] = useState(''), [pending, setPending] = useState(false);
  const [, refreshCallbacks] = useState(0);
  const alive = useRef(true), sequence = useRef(0), request = useRef<AbortController>(), consumed = useRef<LocalSubgraphSource>();
  const latest = useRef(props); latest.current = props;
  const directoryOwner = useRef<{ client: StudioGraphClient; scope: object; identity: string }>();
  const previewOwner = useRef<{ client: StudioGraphClient; scope: object; identity: string }>();
  const owns = (owner: typeof directoryOwner.current) => !!owner && owner.client === props.client && owner.scope === props.scope && owner.identity === props.identity;
  const busyNow = props.locked();
  const values = [props.client, props.identity, props.scope, props.readable, props.blank, busyNow, rows, catalog, choice, text, preview, consent];
  const fence = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const token = fence.current.token;
  const retire = () => { fence.current = { values: fence.current.values, token: {} }; refreshCallbacks(value => value + 1); };
  const valid = () => alive.current && token === fence.current.token && latest.current.readable && latest.current.current();
  const actionable = () => valid() && !latest.current.locked() && !request.current;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; request.current?.abort(); }; }, []);
  useLayoutEffect(() => { if (busyNow) setConsent(''); }, [busyNow]);
  useLayoutEffect(() => {
    sequence.current++; request.current?.abort(); request.current = undefined; consumed.current = undefined;
    setRows([]); setCatalog(undefined); setChoice(''); setText(''); setPreview(undefined); setConsent(''); setError(''); setPending(false);
  }, [props.client, props.identity, props.scope, props.readable]);
  async function load() {
    if (!actionable() || !props.client.localSubgraphCatalog || !props.client.localSubgraphList) return;
    const controller = new AbortController(), epoch = ++sequence.current, source = latest.current;
    request.current = controller; setPending(true); setError(''); setPreview(undefined); setConsent('');
    const current = () => alive.current && !controller.signal.aborted && sequence.current === epoch
      && source.client === latest.current.client && source.scope === latest.current.scope && latest.current.readable && latest.current.current();
    try {
      const [schema, result] = await source.read(() => Promise.all([source.client.localSubgraphCatalog!(controller.signal), source.client.localSubgraphList!(controller.signal)]));
      if (!current()) return;
      directoryOwner.current = { client: source.client, scope: source.scope, identity: source.identity };
      setCatalog(schema); setRows(result.items.filter(row => row.definition.schema_version === 1)); setChoice('');
      source.onCatalog(schema); source.onRecords(result.items);
    } catch (reason) { if (current()) { setRows([]); setCatalog(undefined); setError(apiErrorView(reason, '当前受限目录不可读，旧预览已隐藏。').message); } }
    finally { if (request.current === controller) { request.current = undefined; if (alive.current) setPending(false); } }
  }
  function choose(value: string) {
    if (!actionable()) return;
    retire(); sequence.current++; setChoice(value); setPreview(undefined); setConsent(''); setError('');
  }
  async function verify() {
    if (!actionable() || !catalog || !props.blank || !owns(directoryOwner.current)) return;
    const selected = rows.find(row => row.id === choice); if (!selected) return;
    const controller = new AbortController(), epoch = ++sequence.current, source = latest.current;
    request.current = controller; setPending(true); setPreview(undefined); setConsent(''); setError('');
    const current = () => alive.current && !controller.signal.aborted && sequence.current === epoch
      && source.scope === latest.current.scope && source.client === latest.current.client && latest.current.readable && latest.current.current();
    try {
      const value = await source.read(() => source.client.get(selected.id, controller.signal));
      if (!current()) return;
      if (localSubgraphPinKey(selected) !== localSubgraphPinKey(value)) throw new Error('子图当前版本已变化，旧 pin 未采用；请明确刷新目录并重新选择、核对。');
      previewOwner.current = { client: source.client, scope: source.scope, identity: source.identity };
      setPreview(inspectLocalSubgraphSource(value, catalog));
    } catch (reason) { if (current()) setError(apiErrorView(reason, '子图当前不可用，旧接口与预览已隐藏。').message); }
    finally { if (request.current === controller) { request.current = undefined; if (alive.current) setPending(false); } }
  }
  const key = preview ? JSON.stringify([localSubgraphPinKey(preview.source), text]) : '';
  const visible = props.readable && owns(previewOwner.current) && preview?.source.id === choice ? preview : undefined;
  function edit(value: string) { if (actionable() && props.blank) { retire(); setText(value); setConsent(''); } }
  function confirm(value: boolean) { if (actionable() && visible && props.blank) { retire(); setConsent(value ? key : ''); } }
  function create() {
    if (!actionable() || !visible || !catalog || !props.blank || consent !== key || !key || consumed.current === visible) return;
    consumed.current = visible; retire();
    try {
      const definition = buildLocalSubgraphParent(visible, text);
      if (!latest.current.apply(definition, catalog, props.scope)) throw new Error('目标草稿或权限已变化，未应用；请重新核对。');
      setText(''); setPreview(undefined); setConsent('');
    } catch (reason) { setError(apiErrorView(reason, '父草稿未生成，原图保持不变。').message); }
  }
  return { rows: props.readable && owns(directoryOwner.current) ? rows : [], choice, text, preview: visible, pending, error,
    available: !!props.client.localSubgraphCatalog && !!props.client.localSubgraphList, readable: props.readable,
    blank: props.blank, confirmed: !!key && consent === key, formDirty: !!text,
    load, choose, verify, edit, confirm, create };
}
export type GraphLocalSubgraphParentController = ReturnType<typeof useGraphLocalSubgraphParent>;
