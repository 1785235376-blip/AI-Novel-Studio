import { Button } from '../ui/primitives';
import type { BindingManifest } from './useMultimodalBindingManifest';

export function BindingManifestPanel({ manifest, onRemove }: { manifest: BindingManifest; onRemove: (kind: 'characters' | 'scenes' | 'props', value: string) => void }) {
  const rows: { kind: 'characters' | 'scenes' | 'props'; label: string; value: string }[] = [
    ...manifest.characters.map(value => ({ kind: 'characters' as const, label: '角色', value })),
    ...manifest.scenes.map(value => ({ kind: 'scenes' as const, label: '场景', value })),
    ...manifest.props.map(value => ({ kind: 'props' as const, label: '道具', value })),
  ];
  return <div className="multimodal-director__binding-list">{rows.length ? rows.map(row => <span key={`${row.kind}-${row.value}`}>{row.label}：{row.value}<Button variant="ghost" aria-label={`移除${row.label}绑定 ${row.value}`} onClick={() => onRemove(row.kind, row.value)}>×</Button></span>) : <small className="novel-help">暂无绑定清单</small>}</div>;
}
