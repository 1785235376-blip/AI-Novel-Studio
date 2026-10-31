import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StoryboardProductionPanel } from './StoryboardProductionPanel';
import type { StoryboardProductionProps } from './useStoryboardProductionController';
import type { TimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import type { CreativeDocument } from './types';

export type StudioStoryboardAssetHandoffProps = Omit<StoryboardProductionProps, 'document' | 'onDocument'> & {
  exactImage: TimelineAssetHandoff; onClose: () => void;
};
/** Existing-document selection only; the original production controller owns the binding. */
export function StudioStoryboardAssetHandoff(props: StudioStoryboardAssetHandoffProps) {
  const [rows, setRows] = useState<CreativeDocument[]>([]), [selectedId, setSelectedId] = useState('');
  const [document, setDocument] = useState<CreativeDocument>(), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), slot = useRef(false), epoch = useRef(0), latest = useRef(props); latest.current = props;
  const retired = useRef(false);
  const identity = useRef<unknown[]>([]), values = [props.client, props.studio, props.exactImage, props.active, props.editable, props.isCurrent(), !!props.busy && !props.ownsOperation?.()];
  if (values.some((value, index) => value !== identity.current[index])) { if (identity.current.length) retired.current = true; epoch.current++; identity.current = values; }
  const renderEpoch = epoch.current;
  const current = () => alive.current && !retired.current && latest.current.active && latest.current.isCurrent();
  const locked = !current() || !props.editable || props.busy || props.isBusy() || loading;
  useLayoutEffect(() => { alive.current = true; props.onDirtyChange(true); return () => { alive.current = false; epoch.current++; props.onDirtyChange(false); }; }, []);
  const retiredNow = retired.current;
  useLayoutEffect(() => { if (retiredNow) setLoading(false); }, [retiredNow]);
  const read = async (id?: string) => {
    if (renderEpoch !== epoch.current || !current() || !latest.current.editable || latest.current.busy || latest.current.isBusy() || slot.current || document) return;
    const ticket = ++epoch.current; slot.current = true; setLoading(true); setError('');
    try {
      const value = await props.perform<CreativeDocument | { items: CreativeDocument[] }>(() => id ? props.client.get(id) : props.client.list());
      if (!current() || ticket !== epoch.current) return;
      if ('items' in value) setRows(value.items.filter(row => row.mode === 'STORYBOARD'));
      else if (value.id === id && value.mode === 'STORYBOARD' && Number.isSafeInteger(value.version) && value.version > 0) setDocument(value);
      else throw new Error('目标文档不是所选已有分镜。请重新核对。');
    } catch (reason) { if (current() && ticket === epoch.current) { setError(apiErrorView(reason, '无法读取已有分镜。').message); if (reason instanceof ApiError && [401, 403].includes(reason.status)) props.onDenied(); } }
    finally { slot.current = false; if (alive.current && ticket === epoch.current) setLoading(false); }
  };
  return <section aria-label="已有分镜图片接收器">
    <Button disabled={props.busy || props.isBusy() || loading} onClick={props.onClose}>关闭分镜图片接收器</Button>
    {!current() && <StatusMessage tone="warning">接收身份或操作权限已变化。请关闭后重新选择；原保存结果不会被自动重发。</StatusMessage>}
    <div>
    {document ? <StoryboardProductionPanel {...props} active={props.active && !retired.current} document={document} onDocument={value => { if (current()) setDocument(value); }} /> : current() ? <Panel title="选择已有分镜文档">
      <p>传入图片 {props.exactImage.reference.asset_id} · v{props.exactImage.reference.version}。先选择已存在的分镜文档，再明确选择镜头。</p>
      <Button disabled={locked} onClick={() => void read()}>读取已有分镜文档目录</Button>
      {error && <StatusMessage tone="error">{error}</StatusMessage>}
      <label>已有分镜文档<select disabled={locked} value={selectedId} onChange={event => { if (renderEpoch !== epoch.current || !current() || !latest.current.editable || latest.current.busy || latest.current.isBusy() || slot.current) return; epoch.current++; setSelectedId(event.target.value); }}><option value="">选择已有分镜文档</option>{rows.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></label>
      <Button disabled={locked || !selectedId} onClick={() => void read(selectedId)}>核对所选分镜文档</Button>
    </Panel> : null}
    </div>
  </section>;
}
