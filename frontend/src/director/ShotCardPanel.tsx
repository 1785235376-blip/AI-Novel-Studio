import { Badge } from '../ui/primitives';
import { CameraLanguageControl } from './CameraLanguageControl';
import type { CameraLanguageUsage, ShotCardProjection } from './directorWorkspaceTypes';

/**
 * 一张镜头卡：显示 `SHOT_CARD_FIELDS` 里的全部十一个必填字段。
 *
 * 身份（`shot_id`）与显示序号（`number`）分开显示——这与既有 `ShotCard` owner 和
 * UX-05 镜头卡一致，重排只改序号，不改身份。
 *
 * 每个必填字段都带 `data-field`，所以"十一个字段都显示了"这句话可以被测试核对，
 * 而不是靠人工目测。owner 没有 authoring 的字段显示"原文档未提供"，绝不补一个
 * 看起来合理的值。
 */

const NOT_PROVIDED = '原文档未提供';

export function ShotCardPanel({ card, vocabulary, selected = false, onSelect, onDraftCamera, cameraDraft }: {
  card: ShotCardProjection;
  vocabulary: CameraLanguageUsage['vocabulary'];
  selected?: boolean;
  cameraDraft?: Record<string, string>;
  onSelect?: (shotId: string) => void;
  onDraftCamera?: (shotId: string, field: string, value: string) => void;
}) {
  const missing = (value: string | number | null) => (value === null || value === '' ? NOT_PROVIDED : String(value));
  const cameraField = (field: 'shot_size' | 'camera_motion' | 'lens' | 'composition') => {
    const control = field === 'lens' ? card.lens : field === 'composition' ? card.composition
      : field === 'camera_motion' ? card.movement : undefined;
    const stored = field === 'camera_motion' ? card.camera.camera_motion : card.camera[field];
    const code = control ? control.code : card.camera_classification[field] ?? 'EMPTY';
    return <CameraLanguageControl
      field={field}
      storedValue={stored}
      draftValue={cameraDraft?.[field]}
      code={code}
      members={vocabulary[field]?.members ?? []}
      onDraft={onDraftCamera ? (name, value) => onDraftCamera(card.shot_id, name, value) : undefined}
    />;
  };
  const legacyCount = Object.values(card.camera_classification).filter(code => code === 'LEGACY_PASSTHROUGH').length;
  return <li className="director-shot-card" data-selected={selected ? 'true' : 'false'}>
    <div className="director-shot-card__head">
      {onSelect
        ? <button type="button" className="director-shot-card__identity" aria-pressed={selected}
            aria-label={`镜头 ${card.number ?? card.shot_id}（身份 ${card.shot_id}）`}
            onClick={() => onSelect(card.shot_id)}>SHOT {missing(card.number)}</button>
        : <span className="director-shot-card__identity">SHOT {missing(card.number)}</span>}
      <code className="director-shot-card__id">{card.shot_id}</code>
      {legacyCount > 0 && <Badge tone="warning">旧写法保留 {legacyCount} 项</Badge>}
      <Badge tone={card.camera_canonical_ratio === 1 ? 'success' : 'neutral'}>
        规范取值 {Math.round(card.camera_canonical_ratio * 100)}%
      </Badge>
    </div>

    <dl className="director-shot-card__fields">
      <div data-field="shot_id"><dt>镜头 ID</dt><dd><code>{card.shot_id}</code></dd></div>
      <div data-field="duration"><dt>时长</dt>
        <dd>{card.duration.seconds === null ? NOT_PROVIDED : `${card.duration.seconds} 秒`}</dd></div>
      <div data-field="camera"><dt>摄影机</dt>
        <dd>{cameraField('shot_size')}<span className="director-shot-card__angle">机位角度：{missing(card.camera.angle)}</span></dd></div>
      <div data-field="lens"><dt>镜头</dt><dd>{cameraField('lens')}</dd></div>
      <div data-field="movement"><dt>运动</dt><dd>{cameraField('camera_motion')}</dd></div>
      <div data-field="composition"><dt>构图</dt><dd>{cameraField('composition')}</dd></div>
      <div data-field="lighting"><dt>灯光</dt>
        <dd>{card.lighting.authored ? card.lighting.value : NOT_PROVIDED}</dd></div>
      <div data-field="character"><dt>角色</dt>
        <dd>{card.character.values.length > 0 ? card.character.values.join('、') : NOT_PROVIDED}</dd></div>
      <div data-field="action"><dt>动作</dt>
        <dd>{card.action.authored ? card.action.value : NOT_PROVIDED}</dd></div>
      <div data-field="emotion"><dt>情绪</dt>
        <dd>{card.emotion.authored ? card.emotion.value : NOT_PROVIDED}</dd></div>
      <div data-field="audio"><dt>声音</dt>
        <dd>{card.audio.authored
          ? <span>
              {card.audio.sound && <span>环境声：{card.audio.sound} </span>}
              {card.audio.sound_effect && <span>音效：{card.audio.sound_effect} </span>}
              {card.audio.dialogue.length > 0 && <span>对白 {card.audio.dialogue.length} 条</span>}
            </span>
          : NOT_PROVIDED}</dd></div>
    </dl>

    {card.director_note_ids.length > 0 &&
      <p className="director-shot-card__notes">关联导演备注 {card.director_note_ids.length} 条（原文档）：{card.director_note_ids.join('、')}</p>}
  </li>;
}
