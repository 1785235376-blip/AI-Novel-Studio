import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import { previewCaptionTextReplacement, type CaptionTextReplacement } from './captionTextReplaceHelpers';
import type { CaptionCue, CaptionTrack } from './voiceSubtitleClient';

type Props = { row: CaptionTrack; cues: CaptionCue[]; binding: string; disabled: boolean;
  draftEpoch: { current: number }; admissionEpoch: { current: number }; replace: (cues: CaptionCue[]) => void };
export function CaptionTextReplace(props: Props) {
  const live = useRef(props); live.current = props;
  const alive = useRef(true), owner = useRef({ binding: props.binding }), revision = useRef(0), composing = useRef(false);
  if (owner.current.binding !== props.binding) owner.current = { binding: props.binding };
  const [find, setFind] = useState(''), [replacement, setReplacement] = useState(''), [error, setError] = useState('');
  const [, renderRevision] = useState(0);
  const [page, setPage] = useState(0), [consent, setConsent] = useState<object>();
  const consentRef = useRef<object>(), findInput = useRef<HTMLInputElement>(null), replacementInput = useRef<HTMLTextAreaElement>(null);
  const [preview, setPreview] = useState<{ value: CaptionTextReplacement; owner: object; revision: number; draft: number; admission: number; cues: CaptionCue[]; ticket: object }>();
  const previewRef = useRef(preview), consumed = useRef<object>(); previewRef.current = preview;
  const [undo, setUndo] = useState<{ cues: CaptionCue[]; owner: object; draft: number; admission: number }>();
  const capturedOwner = owner.current, capturedRevision = revision.current;
  const capturedDraft = props.draftEpoch.current, capturedAdmission = props.admissionEpoch.current;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const current = () => alive.current && !live.current.disabled && owner.current === capturedOwner;
  const ready = () => current() && !composing.current && revision.current === capturedRevision
    && props.draftEpoch.current === capturedDraft && props.admissionEpoch.current === capturedAdmission
    && findInput.current?.value === find && replacementInput.current?.value === replacement;
  const invalidate = () => { revision.current++; renderRevision(revision.current); previewRef.current = undefined; setPreview(undefined); consentRef.current = undefined; setConsent(undefined); setError(''); setPage(0); };
  const visible = preview && current() && preview.owner === owner.current && preview.revision === revision.current
    && preview.draft === props.draftEpoch.current && preview.admission === props.admissionEpoch.current
    && preview.cues === props.cues ? preview : undefined;
  const canUndo = undo && current() && undo.owner === owner.current && undo.draft === props.draftEpoch.current && undo.admission === props.admissionEpoch.current;
  return <section aria-label="字幕文本批量替换"><h4>字幕文本查找与替换</h4>
    <p>按原样匹配文字，区分大小写，不使用正则。先预览全部变更，再明确应用到本地；时间、说话人及媒体绑定保持不变。</p>
    <Field label="字幕查找文本"><input ref={findInput} value={find} disabled={props.disabled} maxLength={2000}
      onChange={event => { if (!current()) return; invalidate(); setFind(event.target.value); }}
      onCompositionStart={() => { composing.current = true; invalidate(); }}
      onCompositionEnd={event => { composing.current = false; invalidate(); setFind(event.currentTarget.value); }} /></Field>
    <Field label="字幕替换文本"><textarea ref={replacementInput} value={replacement} disabled={props.disabled} maxLength={20000}
      onChange={event => { if (!current()) return; invalidate(); setReplacement(event.target.value); }}
      onCompositionStart={() => { composing.current = true; invalidate(); }}
      onCompositionEnd={event => { composing.current = false; invalidate(); setReplacement(event.currentTarget.value); }} /></Field>
    <Button disabled={props.disabled || !find || !props.cues.length} onClick={() => {
      if (!ready()) return; invalidate();
      try { const value = previewCaptionTextReplacement(props.row, props.cues, find, replacement);
        if (!value.changes.length) { setError('没有需要替换的文字，本地字幕保持不变。'); return; }
        const next = { value, owner: capturedOwner, revision: revision.current, draft: props.draftEpoch.current,
          admission: props.admissionEpoch.current, cues: props.cues, ticket: {} };
        previewRef.current = next; setPreview(next);
      } catch (reason) { setError(reason instanceof Error ? reason.message : '无法预览字幕替换。'); }
    }}>预览字幕文本替换</Button>
    {!!error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {visible && <section aria-label="字幕文本替换预览">
      <p>{visible.value.changes.length} 条字幕、{visible.value.occurrences} 处文字将替换；每页最多显示 50 条。</p>
      <ol>{visible.value.changes.slice(page * 50, (page + 1) * 50).map(change => <li key={change.id}>
        字幕 {change.index + 1}：原文「{change.before}」 → 替换后「{change.after}」
      </li>)}</ol>
      {visible.value.changes.length > 50 && <><Button disabled={page === 0} onClick={() => setPage(value => Math.max(0, value - 1))}>上一页替换预览</Button>
        <span>第 {page + 1} / {Math.ceil(visible.value.changes.length / 50)} 页</span>
        <Button disabled={(page + 1) * 50 >= visible.value.changes.length} onClick={() => setPage(value => value + 1)}>下一页替换预览</Button></>}
      <label><input type="checkbox" checked={consent === visible.ticket} disabled={props.disabled} onChange={event => {
        if (!ready() || previewRef.current !== visible) return;
        consentRef.current = event.target.checked ? visible.ticket : undefined; setConsent(consentRef.current);
      }} />确认应用全部已列出的替换，仅修改本地字幕</label>
      <Button disabled={props.disabled || consent !== visible.ticket} onClick={() => {
        if (!ready() || previewRef.current !== visible || consentRef.current !== visible.ticket || consumed.current === visible.ticket) return;
        consumed.current = visible.ticket; const before = props.cues.map(cue => ({ ...cue })); invalidate();
        props.replace(visible.value.cues.map(cue => ({ ...cue })));
        setUndo({ cues: before, owner: capturedOwner, draft: props.draftEpoch.current, admission: props.admissionEpoch.current });
      }}>应用字幕文本替换（尚未保存）</Button>
    </section>}
    <Button disabled={!canUndo} onClick={() => {
      if (!canUndo || !undo || !current() || undo.draft !== props.draftEpoch.current || undo.admission !== props.admissionEpoch.current) return;
      invalidate(); setUndo(undefined); props.replace(undo.cues.map(cue => ({ ...cue })));
    }}>撤销上次本地文本替换</Button>
    <p>应用后仍需点击原“保存字幕版本”。再次编辑、刷新或保存后，不再提供这次本地撤销；尚未处理的拆分输入会暂停批量替换。</p>
  </section>;
}
