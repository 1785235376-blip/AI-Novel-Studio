import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { NleEditRequest } from './timelineOpsTypes';
import { selectionRemovePreview } from './timelineSelectionRemove';

/** Review is local; only the explicit button emits the existing remove batch. */
export function SelectionRemovePanel(props: {
  timeline: unknown; selectedClipIds: string[]; editable: boolean;
  isReviewCurrent?: () => boolean; onEdit: (command: NleEditRequest) => void;
}) {
  const alive = useRef(true), latest = useRef(props); latest.current = props;
  const contextKey = JSON.stringify([props.timeline, props.selectedClipIds, props.editable]);
  const context = useRef({ key: contextKey, generation: 0 });
  if (context.current.key !== contextKey) context.current = { key: contextKey, generation: context.current.generation + 1 };
  const generation = context.current.generation, consumed = useRef(-1);
  const [notice, setNotice] = useState<{ generation: number; text: string }>();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  let preview: ReturnType<typeof selectionRemovePreview> | undefined, error = '';
  try { preview = selectionRemovePreview(props.timeline, props.selectedClipIds); }
  catch (reason) { error = reason instanceof Error ? reason.message : '删除预览不可用。'; }
  const remove = () => {
    if (!alive.current || latest.current !== props || context.current.generation !== generation
      || consumed.current === generation || !props.editable || !preview || props.isReviewCurrent?.() === false) return;
    consumed.current = generation;
    props.onEdit({ kind: 'clip.remove', payload: preview.operations });
    setNotice({ generation, text: '已提交所选删除；应用结果见时间线提示，明确保存前不写入服务端。' });
  };
  return <section aria-label="所选片段删除预览">
    <h4>删除所选片段并保留间隙</h4>
    <p>删除 {props.selectedClipIds.length} 个所选片段，不移动其余片段或字幕，不缩短总长，不删除原素材与轨道。</p>
    {preview && <dl className="nle-clip__facts">{preview.targets.map(target => <div key={target.clipId}>
      <dt><code>{target.clipId}</code></dt>
      <dd>{target.kind === 'VIDEO' ? '视频' : '音频'} · <code>{target.trackId}</code> · {target.startMs} — {target.endMs} 毫秒</dd>
    </div>)}</dl>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
    <Button variant="danger" disabled={!props.editable || !preview || consumed.current === generation} onClick={remove}>删除所选片段（保留间隙）</Button>
    <p>整批应用到当前本地草稿，一次撤销可恢复；删空轨道、锁定轨道与悬空转场会整批拒绝。</p>
    {notice?.generation === generation && <StatusMessage>{notice.text}</StatusMessage>}
  </section>;
}
