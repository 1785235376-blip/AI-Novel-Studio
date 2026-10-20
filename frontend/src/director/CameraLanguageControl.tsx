import { Badge } from '../ui/primitives';
import type { ShotValueCode } from './directorWorkspaceTypes';

/**
 * 镜头语言的 UI 绑定。
 *
 * 取值表**只有**一个来源：后端发布的 `camera_language.VOCABULARIES` / `ALIASES`
 * （经 `DirectorIntentProjection` 的 `usage.vocabulary` 传出）。本组件不写死任何
 * 景别/运动/镜头/构图字面量，所以它与 owner 的规范词表不可能漂移。
 *
 * 两条规则写在界面上，而不是写在注释里：
 *  - 原文档里的旧写法**原样保留**并标注"旧写法保留"，绝不折算成某个规范值；
 *  - 只有父级显式给了 `onDraft` 时控件才可交互，且它交付的是**本地草稿**，
 *    本工作区没有任何写回原文档的路径。
 */

/** 纯展示标签。规范**取值**来自后端，这里只有中文名。 */
export const CAMERA_FIELD_LABELS: Record<string, string> = {
  shot_size: '景别', camera_motion: '摄影机运动', lens: '镜头', composition: '构图',
};

export function CameraLanguageControl({ field, storedValue, code, members, disabled, onDraft, draftValue }: {
  field: string;
  storedValue: string;
  draftValue?: string;
  code: ShotValueCode;
  members: string[];
  disabled?: boolean;
  onDraft?: (field: string, value: string) => void;
}) {
  const label = CAMERA_FIELD_LABELS[field] ?? field;
  // 旧写法不在规范表里：把它作为一项保留显示，用户能看到原文。
  const legacy = code === 'LEGACY_PASSTHROUGH' && storedValue !== '';
  const readOnly = disabled || !onDraft;
  return <label className="director-camera">
    <span className="director-camera__label">{label}</span>
    <select
      className="director-camera__select"
      aria-label={label}
      value={draftValue ?? storedValue}
      disabled={readOnly}
      onChange={event => { if (!readOnly) onDraft?.(field, event.target.value); }}
    >
      <option value="">原文档未提供</option>
      {members.map(member => <option key={member} value={member}>{member}</option>)}
      {legacy && <option value={draftValue ?? storedValue}>{storedValue}（旧写法保留）</option>}
    </select>
    {draftValue !== undefined && <span>本地草稿；原值：{storedValue || '未填写'}</span>}
    {code === 'CANONICAL' && <Badge tone="success">规范取值</Badge>}
    {legacy && <Badge tone="warning">旧写法保留</Badge>}
    {code === 'EMPTY' && <Badge tone="neutral">未填写</Badge>}
  </label>;
}
