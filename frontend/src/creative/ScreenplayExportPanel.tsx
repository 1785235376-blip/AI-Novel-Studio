import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import { ApiError } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { CreativeClient, ScreenplayExportFormat } from './client';
import type { CreativeDocument } from './types';

export function ScreenplayExportPanel({ client, document, available, onDenied }: {
  client: CreativeClient; document: CreativeDocument; available: boolean; onDenied: () => void;
}) {
  const [format, setFormat] = useState<ScreenplayExportFormat>('fountain');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const request = useRef<AbortController>();
  const active = useRef(true), allowed = useRef(available);
  allowed.current = available;
  useEffect(() => {
    active.current = true;
    return () => { active.current = false; request.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!available) { request.current?.abort(); setNotice(''); }
  }, [available]);
  const download = async () => {
    if (!available || request.current) return;
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await client.screenplayExport(document, format, controller.signal);
      if (!active.current || !allowed.current || controller.signal.aborted) return;
      const url = URL.createObjectURL(result.blob), anchor = window.document.createElement('a');
      anchor.href = url; anchor.download = result.filename;
      try { anchor.click(); } finally { URL.revokeObjectURL(url); }
      setNotice(`已导出已保存的 v${result.documentVersion}，文件摘要校验通过。`);
    } catch (value) {
      if (!active.current || controller.signal.aborted) return;
      setError(value instanceof ApiError ? value.message : '导出未完成。已保存剧本和本地草稿均未修改，请重试或使用 JSON 导出。');
      if (value instanceof ApiError && [401, 403].includes(value.status)) onDenied();
    } finally {
      if (request.current === controller) request.current = undefined;
      if (active.current) setBusy(false);
    }
  };
  return <section aria-label="剧本文本格式导出">
    <div className="creative-actions"><label className="creative-field"><span>剧本导出格式</span>
      <select value={format} disabled={!available || busy} onChange={event => setFormat(event.target.value as ScreenplayExportFormat)}>
        <option value="fountain">Fountain 剧本文本</option><option value="docx">Word DOCX</option><option value="markdown">Markdown</option>
      </select></label><Button disabled={!available || busy || !document.scenes.length} onClick={() => void download()}><Download aria-hidden="true" />{busy ? '正在导出剧本…' : '导出剧本文本'}</Button></div>
    <p>导出已保存的 v{document.version} 场景、动作、对白和表演提示。结构化角色引用、镜头与导演元数据请保留 JSON 导出；不会生成或修改正文。</p>
    {!available && <StatusMessage>请先保存本地修改并核对版本，再导出剧本。</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="info">{notice}</StatusMessage>}
  </section>;
}
