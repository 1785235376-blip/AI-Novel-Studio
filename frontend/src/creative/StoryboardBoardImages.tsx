import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StoryboardBoardImages } from './useStoryboardBoardImages';

export function StoryboardImageToolbar({ state, dirty }: { state: StoryboardBoardImages; dirty: boolean }) {
  return <section className="storyboard-images-toolbar" aria-label="已保存分镜图片">
    <div className="creative-actions"><Button disabled={!state.canStart} onClick={state.show}>{state.open ? '重新核验本页图片' : '显示已保存分镜图片'}</Button>
      {state.open && <><Button onClick={state.hide}>隐藏图片并释放预览</Button><Button disabled={state.page === 0 || !state.canStart} onClick={() => state.go(state.page - 1)}>上一页图片</Button><Badge>{state.page + 1} / {Math.max(1, state.pages)} 页 · 每页最多 6 镜</Badge><Button disabled={state.page + 1 >= state.pages || !state.canStart} onClick={() => state.go(state.page + 1)}>下一页图片</Button></>}
    </div>
    <p>{dirty ? '当前有未保存更改：保存并重新读取后，才能比较对应版本。' : !state.available ? '需要当前可读取、未阻塞的已保存分镜；图片预览不要求编辑权限。' : '仅按需读取本页正式绑定图片。单图最多 8 MiB / 4,194,304 像素；不读取私有候选，不调用模型。'}</p>
    {state.loading && <StatusMessage>正在核验已保存分镜与正式图片版本…</StatusMessage>}
    {state.problem && <StatusMessage tone="warning">{state.problem}</StatusMessage>}
  </section>;
}
export function StoryboardCardImage({ state, shotId }: { state: StoryboardBoardImages; shotId: string }) {
  if (!state.open) return null;
  const row = state.rows.find(row => row.shot_id === shotId), image = state.thumbnail(shotId);
  return <span className="storyboard-card-image" aria-label={`镜头 ${row?.shot.number ?? shotId} 图片缩略图`}>
    {image?.url ? <img src={image.url} alt={`SHOT ${row!.shot.number} 正式绑定图片 v${row!.image_asset!.version}`} />
      : <span role={image?.state === 'LOADING' ? 'status' : undefined}>{image?.problem ?? (!state.receipt ? '正在读取绑定…' : !row?.image_asset ? '未绑定正式图片' : image?.state === 'LOADING' ? '正在核验图片…' : '图片等待读取')}</span>}
  </span>;
}
export function StoryboardImageComparison({ state }: { state: StoryboardBoardImages }) {
  if (!state.open || !state.receipt) return null;
  const row = state.selected, image = state.comparison;
  return <section className="storyboard-image-comparison" aria-label="已保存镜头图文比较">
    <h3>已保存镜头 · 图文比较</h3>
    {!row ? <p>选中镜头不在当前图片页。请切换图片页或在本页选择镜头。</p> : <>
      <p>分镜 v{state.receipt.document_snapshot.version} · 镜头 {row.shot_id} v{row.shot_version}{row.image_asset ? ` · 正式图片 ${row.image_asset.asset_id} v${row.image_asset.version}` : ' · 未绑定正式图片'}</p>
      <div className="storyboard-image-comparison__sides"><div><h4>已保存文字</h4><p>{row.shot.frame_prompt || '原文档未提供画面描述'}</p><p>{row.shot.action || '原文档未提供动作'}</p><dl><div><dt>景别 / 角度</dt><dd>{row.shot.shot_size || '未提供'} / {row.shot.camera_angle || '未提供'}</dd></div><div><dt>运镜 / 镜头</dt><dd>{row.shot.camera_motion || '未提供'} / {row.shot.lens || '未提供'}</dd></div><div><dt>构图</dt><dd>{row.shot.composition || '未提供'}</dd></div><div><dt>灯光 / 色彩</dt><dd>{row.shot.lighting || '未提供'} / {row.shot.color || '未提供'}</dd></div></dl></div>
        <div><h4>正式绑定图片</h4>{image?.url ? <img src={image.url} alt={`SHOT ${row.shot.number} 图文比较图片`} /> : <p role="status">{image?.problem ?? (!row.image_asset ? '未绑定正式图片。请使用原素材绑定与审核流程。' : image?.state === 'LOADING' ? '正在核验比较图片…' : '比较图片等待读取')}</p>}</div></div>
      <p>这里只显示核验过的保存版本与缩放预览，不判断构图、人物或连续性是否正确。原图、分镜、批准和绑定均未修改；来源变化后需重新核验。</p>
    </>}
  </section>;
}
