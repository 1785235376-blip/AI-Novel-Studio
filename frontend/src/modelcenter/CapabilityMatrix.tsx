import { Badge, Button, EmptyState } from '../ui/primitives';
import { MODEL_CENTER_MODALITIES, type CapabilityMatrix } from './modelCenterTypes';

/** 模态的中文标签。纯呈现，不改变任何 owner 事实。 */
export const MODALITY_LABELS: Readonly<Record<typeof MODEL_CENTER_MODALITIES[number], string>> = Object.freeze({
  text: '文本', image: '图像', video: '视频', audio: '音频',
});

/**
 * 能力矩阵：声明与已验证分成两列语义，`undeclared` / `declared_only` / `verified`
 * 三态各自可断言。没有任何"把声明升级为已验证"的路径。
 */
export function CapabilityMatrix({ matrix, onSelect, selected }: {
  matrix: CapabilityMatrix; onSelect: (modelId: string) => void; selected?: string;
}) {
  if (!matrix.rows.length) {
    return <EmptyState title="没有注册模型" detail="原 owner 的模型注册表返回为空：这不是读取失败，也不是权限被拒。" />;
  }
  return (
    <div className="model-center__matrix" role="region" aria-label="能力矩阵：声明与已验证">
      <p className="model-center__hint">
        每一格都同时显示"声明"与"已验证"。声明能力永远不会被提升为已验证能力：
        只有原 owner 的校验记录（model.verified / hardware_profile.tested）与运行时能力快照
        同时成立，才会显示为"已验证"。
        {!matrix.runtime_observation_available && ' 当前没有读取到任何运行时能力快照，因此全部只能是"仅声明"。'}
      </p>
      <table>
        <caption className="model-center__caption">模型 × 模态（声明 / 已验证）</caption>
        <thead>
          <tr>
            <th scope="col">模型</th>
            {matrix.modalities.map(modality => <th scope="col" key={modality}>{MODALITY_LABELS[modality]}</th>)}
            <th scope="col">原 owner 能力码</th>
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map(row => (
            <tr key={row.model_id} aria-selected={row.model_id === selected || undefined}>
              <th scope="row">
                <Button variant="ghost" onClick={() => onSelect(row.model_id)}>{row.display_name}</Button>
                {row.model_id === selected && <Badge tone="info">当前查看</Badge>}
              </th>
              {row.cells.map(cell => (
                <td key={cell.modality} title={cell.evidence} data-capability-state={cell.state}>
                  {cell.state === 'undeclared' && <Badge tone="neutral">未声明</Badge>}
                  {cell.state === 'declared_only' && <Badge tone="warning">仅声明</Badge>}
                  {cell.state === 'verified' && <Badge tone="success">已验证</Badge>}
                </td>
              ))}
              <td>{row.declared_capabilities.join('、') || '无'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {matrix.rows.filter(row => row.unknown_reason).map(row => (
        <p className="model-center__hint" key={row.model_id}>{row.display_name}：{row.unknown_reason}</p>
      ))}
    </div>
  );
}
