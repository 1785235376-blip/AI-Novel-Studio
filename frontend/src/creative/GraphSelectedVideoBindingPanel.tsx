import { Button, StatusMessage } from '../ui/primitives';
import { useRef } from 'react';
import { mediaProviderKey } from './useStudioMediaExecution';
import type { useGraphSelectedVideoBinding } from './useGraphSelectedVideoBinding';

export function GraphSelectedVideoBindingPanel({ binding }: { binding: ReturnType<typeof useGraphSelectedVideoBinding> }) {
  const choiceInput = useRef<HTMLSelectElement>(null);
  const withCurrentChoice = (work: () => void) => { if (choiceInput.current?.value === binding.choice) work(); else binding.cancel(); };
  return <section aria-label="所选视频节点本地批量绑定">
    <h3>所选视频节点 · 本地模型绑定</h3>
    <p>明确选择 1–4 个同一操作的视频生成节点。只更新服务商、模型和 allow_cloud=false；其他参数与来源保持。保存与执行仍需另行操作。</p>
    {binding.selectionError && <p>{binding.selectionError}</p>}
    <Button disabled={!binding.canRead || binding.loading} loading={binding.loading} onClick={() => void binding.load()}>读取批量绑定本地配置</Button>
    <label>批量绑定本地服务商与模型<select ref={choiceInput} disabled={!binding.canChoose} value={binding.choice} onChange={event => binding.choose(event.target.value)}>
      <option value="">明确选择本地配置</option>
      {binding.rows.map(row => <option key={mediaProviderKey(row)} value={mediaProviderKey(row)}>{row.provider_id} · {row.model_id}</option>)}
    </select></label>
    <p>CONFIGURED_NOT_VERIFIED：仅发现已有本地配置，尚未验证推理。</p>
    <Button disabled={!binding.canChoose || !binding.choice} onClick={() => withCurrentChoice(binding.prepare)}>预览所选视频节点绑定</Button>
    {binding.error && <StatusMessage tone="warning">{binding.error}</StatusMessage>}
    {binding.preview && <div aria-label="所选视频节点绑定预览" role="status">
      <ul>{binding.preview.changes.map(row => <li key={row.nodeId}>{row.nodeId}：provider_id {row.before.provider_id || '空'} → {row.after.provider_id}；model_id {row.before.model_id || '空'} → {row.after.model_id}；allow_cloud {String(row.before.allow_cloud ?? false)} → false</li>)}</ul>
      <p>确认将以上绑定一次应用到本地草稿，可一次撤销或重做；不会保存或启动任务。</p>
      <Button disabled={!binding.canChoose} onClick={() => withCurrentChoice(() => { binding.apply(); })}>确认应用所选视频节点本地绑定</Button>
      <Button onClick={binding.cancel}>取消视频绑定预览</Button>
    </div>}
  </section>;
}
