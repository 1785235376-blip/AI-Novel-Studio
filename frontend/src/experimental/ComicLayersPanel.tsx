import { useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import type { ComicDocument, ComicLayer } from './comicLayoutsClient';
import { comicLayerKindLabel, comicLayersError, enableComicLayers } from './comicLayers';

type Props = { document: ComicDocument; disabled: boolean; onChange: (next: ComicDocument) => void };
export function ComicLayersPanel({ document, disabled, onChange }: Props) {
  const [error, setError] = useState('');
  const stack = document.layer_stack, invalid = comicLayersError(document);
  const patch = (id: string, values: Partial<ComicLayer>) => {
    if (disabled || invalid || !stack) return;
    onChange({ ...document, layer_stack: { ...stack, items: stack.items.map(layer => layer.id === id ? { ...layer, ...values } : layer) } });
  };
  const move = (index: number, direction: -1 | 1) => {
    if (disabled || invalid || !stack || index + direction < 0 || index + direction >= stack.items.length) return;
    const items = [...stack.items]; [items[index], items[index + direction]] = [items[index + direction], items[index]];
    onChange({ ...document, layer_stack: { ...stack, items } });
  };
  return <details aria-label="漫画可编辑图层" open={!!stack}>
    <summary>可编辑图层 {stack && <Badge>{stack.items?.length ?? 0} 层</Badge>}</summary>
    <p>图片、格框边框、气泡形状和气泡文字可分别命名、隐藏、调整透明度和叠放顺序。图层名称须为 1–120 个字符。对白仍在下方气泡文字框编辑；图层引用同一份原生内容与坐标。</p>
    {!stack && <><p>此页面尚未启用图层。启用时按当前阅读顺序保留原叠放顺序；不会自动保存或批准。</p><Button disabled={disabled} onClick={() => {
      if (disabled) return;
      try { setError(''); onChange(enableComicLayers(document)); } catch (reason) { setError(reason instanceof Error ? reason.message : '无法启用图层。'); }
    }}>为当前草稿启用图层</Button></>}
    {(invalid || error) && <StatusMessage tone="warning">{invalid || error}</StatusMessage>}
    {stack && !invalid && <>
      <p>列表从最上层到最下层显示。新增格框或气泡的图层放在最上方；删除内容仅移除对应图层。调整后须保存、预检并重新核对像素。</p>
      {!stack.items.length && <StatusMessage>页面为空。添加格框后会建立图片与边框图层，有意留白的格框也保留图片图层。</StatusMessage>}
      <ol aria-label="图层叠放顺序（从上到下）">{[...stack.items].reverse().map((layer, index) => {
        const storedIndex = stack.items.length - 1 - index, label = `图层 ${index + 1}`;
        return <li key={layer.id} className="experimental-record">
          <Badge>{comicLayerKindLabel[layer.kind]}</Badge><span> · {layer.target_id}</span>
          <fieldset className="experimental-form" disabled={disabled}>
            <Field label={`${label} 名称`}><input minLength={1} maxLength={120} value={layer.name} onChange={event => patch(layer.id, { name: event.target.value })} /></Field>
            <label className="experimental-check"><input type="checkbox" checked={layer.visible} onChange={event => patch(layer.id, { visible: event.target.checked })} />{label} 可见</label>
            <Field label={`${label} 不透明度 (%)`}><input type="number" min={0} max={100} step={1} value={layer.opacity_percent} onChange={event => {
              const value = event.target.valueAsNumber; if (Number.isInteger(value) && value >= 0 && value <= 100) patch(layer.id, { opacity_percent: value });
            }} /></Field>
            <div className="experimental-actions"><Button disabled={index === 0} onClick={() => move(storedIndex, 1)}>上移{label}</Button><Button disabled={storedIndex === 0} onClick={() => move(storedIndex, -1)}>下移{label}</Button></div>
          </fieldset>
        </li>;
      })}</ol>
      <StatusMessage>OpenRaster（ORA）导出会把文字与形状栅格化为独立图层；原生项目保留可编辑对白。目前不支持 ORA 导入。</StatusMessage>
    </>}
  </details>;
}
