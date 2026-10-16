import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StudioBinaryMaskCanvas } from './StudioBinaryMaskCanvas';
import { useStudioManualMask, type StudioManualMaskProps } from './useStudioManualMask';

/** A local authoring surface in the original Image workspace, not a job owner. */
export function StudioManualMaskPanel(props: StudioManualMaskProps & { onOpenAsset: (id: string) => void; onRefreshAssets: () => void }) {
  const mask = useStudioManualMask(props);
  if (mask.unavailable) return null;
  return <Panel title="手工二值遮罩" aria-label="手工二值遮罩">
    <p>从当前 PNG 原始文件创建独立遮罩资产。仅支持非隔行 8 位 PNG（仅 IHDR / IDAT / IEND 块；含颜色配置、文字或其它附加信息的 PNG 暂不支持），宽高 64–1024 且为 8 的倍数，最多 8 MiB；不自动缩放或转换。</p>
    <p>白色保留，黑色移除。保存只创建原资产库中的 PNG；不会自动生成任务、调用模型或执行抠图。</p>
    {!mask.eligible && <StatusMessage tone="warning">请选择可读取当前版本的 PNG 图片资产。</StatusMessage>}
    {!mask.editor && !mask.attempt && <Button disabled={!mask.canLoad} onClick={() => void mask.load()}>核对来源并打开遮罩编辑</Button>}
    {mask.pending && <StatusMessage>{mask.pending === 'LOAD' ? '正在读取、校验并解码来源…' : '正在保存遮罩，请等待结果确认…'}</StatusMessage>}
    {mask.editor && <>
      <p>来源 {mask.editor.source.filename} · v{mask.editor.source.version} · {mask.editor.mask.width} × {mask.editor.mask.height}</p>
      <StudioBinaryMaskCanvas mask={mask.editor.mask} sourceUrl={mask.editor.url} readOnly={!mask.editable} isCurrent={mask.isEditable} onChange={mask.changed} />
      {!mask.mixed && <StatusMessage>遮罩需要同时包含保留和移除像素，且结束当前笔画后才能保存。</StatusMessage>}
      {!mask.attempt && <><label><input type="checkbox" checked={mask.consent} disabled={!mask.editable || !mask.mixed} onChange={event => mask.agree(event.target.checked)} />确认将当前黑白像素保存为新遮罩资产</label>
        <Button disabled={!mask.canSave} onClick={() => void mask.save()}>保存二值遮罩</Button></>}
      {mask.attempt && <Button disabled={!!mask.pending || props.busy || !mask.attempt.retryable} onClick={() => void mask.save(true)}>明确重试同一遮罩保存</Button>}
      <Button disabled={!!mask.pending} onClick={mask.discard}>丢弃本地遮罩</Button>
    </>}
    {mask.message && <StatusMessage tone={mask.attempt ? 'warning' : 'info'}>{mask.message}</StatusMessage>}
    {mask.attempt && <Button disabled={props.busy || !!mask.pending} onClick={props.onRefreshAssets}>刷新原资产列表核对结果</Button>}
    {mask.result && <Button disabled={props.busy} onClick={() => props.onOpenAsset(mask.result!.asset.id)}>查看已保存遮罩资产</Button>}
  </Panel>;
}
