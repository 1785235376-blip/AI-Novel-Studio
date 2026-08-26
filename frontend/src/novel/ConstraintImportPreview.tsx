import { Button } from '../ui/primitives';

export function ConstraintImportPreview({ value, currentMode, onConfirm, onCancel }: { value: any; currentMode?: 'image' | 'video'; onConfirm: () => void; onCancel: () => void }) {
  const shots = Array.isArray(value?.shots) ? value.shots : [];
  const confirmed = shots.filter((shot: any) => shot.constraint_status === 'confirmed').length;
  const pending = shots.filter((shot: any) => ['saving', 'pending_confirmation'].includes(shot.constraint_status)).length;
  const failed = shots.filter((shot: any) => shot.constraint_status === 'failed').length;
  const unsaved = shots.filter((shot: any) => !shot.constraint_status).length;
  const mismatch = Boolean(currentMode && value?.mode && currentMode !== value.mode);
  const confirm = () => { if (!mismatch || window.confirm(`约束包模式为${value.mode}，当前工作区为${currentMode}。仍要导入吗？`)) onConfirm(); };
  return <div className="notice" role="dialog"><strong>导入预览</strong><p>模式：{value?.mode || '未标记'} · 视图：{value?.editor_view || '未标记'}</p><p>参考：{value?.references?.length || 0} · 镜头：{shots.length}</p>{shots.length > 0 && <p>镜头约束：已确认 {confirmed} · 待确认 {pending} · 失败 {failed} · 未保存 {unsaved}</p>}{failed > 0 && <p role="alert">该约束包包含 {failed} 个保存失败的镜头，导入后需要重新绑定或保存约束。</p>}{mismatch && <p role="alert">约束包模式与当前工作区不匹配，确认导入时需要再次确认。</p>}<Button onClick={confirm}>确认导入</Button><Button variant="ghost" onClick={onCancel}>取消</Button></div>;
}
