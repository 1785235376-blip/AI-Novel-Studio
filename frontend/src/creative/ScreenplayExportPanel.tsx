import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import { ApiError } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { CreativeClient, ScreenplayExportFormat, ScriptExportFormat } from './client';
import type { CreativeDocument } from './types';

export function ScreenplayExportPanel({ client, document, available, onDenied }: {
  client: CreativeClient; document: CreativeDocument; available: boolean; onDenied: () => void;
}) {
  const script = document.mode === 'SCRIPT';
  const noun = script ? '脚本' : '剧本';
  const [format, setFormat] = useState<ScreenplayExportFormat | ScriptExportFormat>(script ? 'txt' : 'fountain');
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
      const result = await (script ? client.scriptExport(document, format as ScriptExportFormat, controller.signal) : client.screenplayExport(document, format as ScreenplayExportFormat, controller.signal));
      if (!active.current || !allowed.current || controller.signal.aborted) return;
      const url = URL.createObjectURL(result.blob), anchor = window.document.createElement('a');
      anchor.href = url; anchor.download = result.filename;
      try { anchor.click(); } finally { URL.revokeObjectURL(url); }
      setNotice(`已导出已保存的 v${result.documentVersion}，文件摘要校验通过。`);
    } catch (value) {
      if (!active.current || controller.signal.aborted) return;
      setError(value instanceof ApiError ? value.message : `导出未完成。已保存${noun}和本地草稿均未修改，请重试或使用 JSON 导出。`);
      if (value instanceof ApiError && [401, 403].includes(value.status)) onDenied();
    } finally {
      if (request.current === controller) request.current = undefined;
      if (active.current) setBusy(false);
    }
  };
  return <section aria-label={script ? '通用脚本文本格式导出' : '剧本文本格式导出'}>
    <div className="creative-actions"><label className="creative-field"><span>{noun}导出格式</span>
      <select aria-label={`${noun}导出格式`} value={format} disabled={!available || busy} onChange={event => setFormat(event.target.value as ScreenplayExportFormat | ScriptExportFormat)}>
        {script ? <option value="txt">纯文本 TXT</option> : <option value="fountain">Fountain 剧本文本</option>}<option value="docx">Word DOCX</option><option value="markdown">Markdown</option>{!script && <option value="epub">EPUB 电子书</option>}
      </select></label><Button disabled={!available || busy || (script ? !document.script?.body : !document.scenes.length)} onClick={() => void download()}><Download aria-hidden="true" />{busy ? `正在导出${noun}…` : `导出${noun}文本`}</Button></div>
    <p>{script ? `导出已保存的 v${document.version} 通用脚本。TXT/Markdown 保留原文；Word 包含标题与原文。完整版本与来源信息请保留 JSON；不会修改小说正文。` : `导出已保存的 v${document.version} 场景、动作、对白和表演提示。EPUB 是可导航的重排阅读版，不保证专业分页。结构化角色引用、镜头与导演元数据请保留 JSON 导出；不会生成或修改正文。`}</p>
    {!available && <StatusMessage>请先保存本地修改并核对版本，再导出{noun}。</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="info">{notice}</StatusMessage>}
  </section>;
}
