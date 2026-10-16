import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { CreativeClient } from './client';
import type { ScreenplayPreset } from './screenplayPresets';

export function ScreenplayPresetPanel({ client, available, onUse, onDenied }: { client: CreativeClient; available: boolean; onUse: (preset: ScreenplayPreset) => void; onDenied: () => void }) {
  const [open, setOpen] = useState(false), [attempt, setAttempt] = useState(0), [loading, setLoading] = useState(false), [error, setError] = useState(''), [items, setItems] = useState<ScreenplayPreset[]>([]), [selected, setSelected] = useState('');
  const epoch = useRef(0);
  useEffect(() => {
    const ticket = ++epoch.current, controller = new AbortController(); setItems([]); setSelected(''); setError('');
    if (!open) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    client.screenplayPresets(controller.signal).then(result => {
      if (controller.signal.aborted || ticket !== epoch.current) return;
      setItems(result.templates); setSelected(result.templates[0]?.id || '');
    }).catch(value => {
      if (controller.signal.aborted || ticket !== epoch.current) return;
      if (value instanceof ApiError && [401, 403].includes(value.status)) onDenied();
      else setError('起稿模板未能读取。当前草稿保持不变，可以重试。');
    }).finally(() => { if (!controller.signal.aborted && ticket === epoch.current) setLoading(false); });
    return () => { controller.abort(); epoch.current++; };
  }, [client, open, attempt]);
  const chosen = items.find(row => row.id === selected);
  return <section aria-label="独立剧本起稿模板">
    <Button aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? '收起起稿模板' : '浏览起稿模板'}</Button>
    {open && <>
      <p>模板只提供可编辑的线性写作提示。使用后建立新的未保存独立剧本，不读取章节、不调用模型；现有文档仍保留。游戏分支暂不支持。</p>
      {loading && <StatusMessage>正在读取起稿模板…</StatusMessage>}
      {error && <><StatusMessage tone="error">{error}</StatusMessage><Button onClick={() => setAttempt(value => value + 1)}>重试起稿模板</Button></>}
      {!!items.length && <><label className="creative-field"><span>起稿类型</span><select aria-label="起稿类型" value={selected} onChange={event => setSelected(event.target.value)}>{items.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        {chosen && <><p>{chosen.description} · 模板 v{chosen.version}</p><ol>{chosen.document.scenes.map(scene => <li key={scene.id}><strong>{scene.heading}</strong><p>{scene.action}</p></li>)}</ol>
          <Button disabled={!available || loading} onClick={() => onUse(chosen)}>从模板新建未保存剧本</Button></>}
      </>}
      {!available && <StatusMessage>请先保存或处理当前草稿，并确认编辑权限；模板不会覆盖未保存或待核对的内容。</StatusMessage>}
    </>}
  </section>;
}
