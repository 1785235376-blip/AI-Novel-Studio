import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { continuityOf, neighbourOf, STORYBOARD_DRAFT_NOTICE } from './storyboardOps';
import { SHOT_ACTION_LABELS } from './storyboardWorkspaceTypes';
import type { DirectorVsShotResolution, StoryboardShot, StoryboardShotRow } from './storyboardWorkspaceTypes';

/**
 * 单镜头详情：每个事实**逐条**列出它的来源；缺席的字段显示"原文档未提供"，
 * 由 `ShotSummary.evidence.absent` 驱动，所以界面无法补一个看起来合理的默认值。
 *
 * 参考比较：这里只比较原 owner 明写的原版本（镜头版本 / 已绑定素材版本 /
 * 视频来源镜头版本）。没有证据就不给结论，更没有"连续性没问题"这种保证。
 */
export function ShotDetailPanel({ row, neighbours, onCompare, onPrepareDraft, comparison, resolution, locked }: {
  row: StoryboardShotRow | undefined;
  neighbours: (direction: 'PREVIOUS' | 'NEXT') => { neighbour: StoryboardShot | null; declared: string | null };
  onCompare: () => void;
  onPrepareDraft: (target: 'IMAGE' | 'VIDEO' | 'TIMELINE') => void;
  comparison: { kind: 'IMAGE' | 'VIDEO'; asset_id: string; version: number; digest: string; matches_version: boolean } | null;
  resolution: DirectorVsShotResolution | null;
  locked: boolean;
}) {
  if (!row) {
    return <Panel title="镜头详情">
      <EmptyState title="尚未选中镜头" detail="在上面的镜头清单里选择一个镜头；列表、详情与送往面板始终共用同一个选择。" />
    </Panel>;
  }
  const { shot, summary } = row;
  const fact = (label: string, value: string | number | null | undefined) =>
    <div><dt>{label}</dt><dd>{value === null || value === undefined || value === '' ? '原文档未提供' : String(value)}</dd></div>;
  const previous = neighbours('PREVIOUS'), next = neighbours('NEXT');
  const video = shot.video_result;
  const videoSourceMatches = !!video && video.source_shot.shot_version === shot.shot_version && video.source_shot.shot_digest === shot.shot_digest;
  const shown = resolution?.shot_id === summary.shot_id ? resolution : null;

  return <Panel title={`镜头详情 · SHOT ${summary.number}`}>
    <header className="storyboard-shot-detail__header">
      <Badge tone="neutral">身份 {summary.shot_id}</Badge>
      <Badge tone="neutral">显示序号 {summary.number}</Badge>
      <Badge tone="neutral">镜头版本 v{shot.shot_version}</Badge>
      <Badge tone={shot.image_asset ? 'success' : 'warning'}>{shot.image_asset ? '已绑定正式图片' : '未绑定正式图片'}</Badge>
      <Badge tone={video ? 'success' : 'neutral'}>{video ? '已绑定正式视频' : '未绑定正式视频'}</Badge>
    </header>

    <dl className="storyboard-shot-detail__facts">
      {fact('所属场景', summary.scene_id)}
      {fact('时长（秒）', summary.duration?.seconds ?? null)}
      {fact('景别', summary.framing.shot_size)}
      {fact('机位角度', summary.framing.camera_angle)}
      {fact('摄影机运动', summary.framing.camera_motion)}
      {fact('镜头/焦段', summary.framing.lens)}
      {fact('构图', summary.framing.composition)}
      {fact('光线', summary.lighting_color.lighting)}
      {fact('色彩', summary.lighting_color.color)}
      {fact('环境', summary.lighting_color.environment)}
      {fact('音效', summary.audio?.sound_effect ?? null)}
      {fact('声音', summary.audio?.sound ?? null)}
    </dl>

    <section aria-label="原文档证据">
      <h4>原文档证据</h4>
      <p>这些字段读到了：{summary.evidence.fields.join('、') || '一个都没有'}。</p>
      <p>这些字段原文档没有提供：{summary.evidence.absent.join('、') || '没有缺席字段'}。</p>
      <details><summary>镜头内容摘要（原 owner 的 shot_digest）</summary><code>{shot.shot_digest}</code></details>
    </section>

    <section aria-label="相邻镜头">
      <h4>相邻镜头</h4>
      <p>前一个：{previous.neighbour ? `SHOT ${previous.neighbour.shot.number}（${previous.neighbour.shot_id}）` : '这是第一个镜头（边界，不回绕）'}</p>
      <p>后一个：{next.neighbour ? `SHOT ${next.neighbour.shot.number}（${next.neighbour.shot_id}）` : '这是最后一个镜头（边界，不回绕）'}</p>
      <p>原文档声明的邻居：前 {continuityOf(shot, 'PREVIOUS') ?? '未声明'} · 后 {continuityOf(shot, 'NEXT') ?? '未声明'}（声明值就是原文档事实，本工作区不改写它）。</p>
    </section>

    <section aria-label="镜头引用">
      <h4>引用与一致性要求</h4>
      <p>角色：{summary.references.characters.join('、') || '原文档未提供'}</p>
      <p>关联导演备注：{summary.references.director_note_ids.join('、') || '原文档未提供'}</p>
      {summary.references.continuity
        ? <p>一致性要求：{summary.references.continuity.fidelity.join(' · ') || '原文档未提供细节'}</p>
        : <p>原文档没有声明一致性要求（这里不会替你判断"连续性没问题"）。</p>}
    </section>

    <section aria-label="参考比较">
      <h4>参考比较</h4>
      <Button disabled={locked || !shot.image_asset && !video} onClick={onCompare}>只读比较绑定素材与镜头版本</Button>
      {summary.candidate
        ? <p>当前候选来源：{summary.candidate.kind} {summary.candidate.ref.asset_id} · v{summary.candidate.ref.version}</p>
        : <p>这个镜头还没有正式绑定的候选素材。</p>}
      {comparison && <div className="storyboard-shot-detail__comparison">
        <p>{comparison.kind} {comparison.asset_id} · v{comparison.version}</p>
        <p>{comparison.matches_version
          ? '这条素材记录与镜头当前版本一致（按原 owner 记下的版本针比较）。'
          : '注意：这条素材记录与镜头当前版本不一致。上面的不一致证据优先于任何结论。'}</p>
        <code>{comparison.digest}</code>
      </div>}
      {video && !videoSourceMatches && <StatusMessage tone="warning">
        已绑定视频来自快门版本（来源镜头 v{video.source_shot.shot_version}），当前镜头是 v{shot.shot_version}。它仍然存在，但不再代表当前内容。
      </StatusMessage>}
      {summary.staleness.length > 0
        ? <ul>{summary.staleness.map((note, index) => <li key={`${note.kind}-${index}`}>
          <Badge tone="warning">{note.kind}</Badge> {note.detail}
          {note.expected && <code>{note.expected.id} v{note.expected.version}</code>}
          {note.actual && <code>{note.actual.id} v{note.actual.version}</code>}
        </li>)}</ul>
        : <p>没有读到有证据的来源不一致。这不是"连续性没问题"的保证，只是这次读取没有发现不一致。</p>}
    </section>

    {shown && <section aria-label="导演目标与镜头覆写">
      <h4>导演目标 vs 镜头级覆写</h4>
      <p>继承来源：{shown.inherited_from_note_ids.join('、') || '没有继承依据（这个镜头没有关联导演备注）'}</p>
      <ul>{shown.fields.map(field => <li key={field.field}>
        {field.field}：镜头 {field.shot_value ?? '—'} · 导演 {field.inherited_value ?? '—'} · 生效 {field.effective === 'SHOT_OVERRIDE' ? '镜头级覆写' : field.effective === 'DIRECTOR_INHERITED' ? '继承导演目标' : '双方都没有提供'}
        {field.overridden && <Badge tone="warning">覆写生效</Badge>}
      </li>)}</ul>
      <p>修改导演目标不会改写已经批准的下游结果：本工作区只读，导演文档与镜头文档都不在这里被写入。</p>
    </section>}

    <section aria-label="镜头下一步">
      <h4>下一步可做的事</h4>
      {summary.next_actions.length > 0
        ? <ul>{summary.next_actions.map(action => <li key={action}>{SHOT_ACTION_LABELS[action]}</li>)}</ul>
        : <p>原文档没有声明任何可用的下一步。</p>}
      <Button disabled={locked} onClick={() => onPrepareDraft('IMAGE')}>准备图片请求草稿</Button>
      <Button disabled={locked} onClick={() => onPrepareDraft('VIDEO')}>准备视频请求草稿</Button>
      <Button disabled={locked} onClick={() => onPrepareDraft('TIMELINE')}>准备时间线底稿请求</Button>
      <p>{STORYBOARD_DRAFT_NOTICE}</p>
    </section>
  </Panel>;
}
