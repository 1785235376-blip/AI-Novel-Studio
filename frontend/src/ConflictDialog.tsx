import { useEffect, useId, useRef, useState } from 'react';
import {
  conflictResolutionDrafts,
  PersistentConflict,
  type ConflictResolutionDraft,
} from './drafts';

type ConflictDialogProps = {
  value: PersistentConflict;
  namespace?: string;
  onUseServer: () => void;
  onClose: () => void;
  onResolutionDraft?: (draft: ConflictResolutionDraft) => void;
};

export function ConflictDialog({
  value,
  namespace = 'file',
  onUseServer,
  onClose,
  onResolutionDraft,
}: ConflictDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const first = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLElement>(null);
  const savedResolution = conflictResolutionDrafts.load(value.chapterId, namespace);
  const [resolution, setResolution] = useState(
    savedResolution?.sourceConflictDetectedAt === value.detectedAt
      ? savedResolution.content
      : value.local.content,
  );
  const [resolutionStatus, setResolutionStatus] = useState('');
  const [copyStatus, setCopyStatus] = useState('');

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    first.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab') return;
      const nodes = [
        ...(dialog.current?.querySelectorAll<HTMLElement>(
          'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])',
        ) ?? []),
      ].filter(node => !node.hasAttribute('disabled'));
      if (!nodes.length) return;
      const firstNode = nodes[0];
      const lastNode = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === firstNode) {
        event.preventDefault();
        lastNode.focus();
      } else if (!event.shiftKey && document.activeElement === lastNode) {
        event.preventDefault();
        firstNode.focus();
      }
    };
    addEventListener('keydown', handleKey);
    return () => {
      removeEventListener('keydown', handleKey);
      previous?.focus();
    };
  }, [onClose]);

  const useServer = () => {
    conflictResolutionDrafts.remove(value.chapterId, namespace);
    dispatchEvent(
      new CustomEvent('studio:use-server-version', {
        detail: { chapterId: value.chapterId, server: value.server },
      }),
    );
    onUseServer();
  };

  const saveResolution = () => {
    const draft: ConflictResolutionDraft = {
      chapterId: value.chapterId,
      content: resolution,
      serverVersion: value.server.version,
      sourceConflictDetectedAt: value.detectedAt,
      updatedAt: new Date().toISOString(),
    };
    conflictResolutionDrafts.save(draft, namespace);
    dispatchEvent(new CustomEvent('studio:conflict-resolution-draft', { detail: draft }));
    onResolutionDraft?.(draft);
    setResolutionStatus('手工解决草稿已保存，本地草稿和冲突记录均未丢弃。');
  };
  const copyLocal = async () => {
    try {
      await navigator.clipboard.writeText(value.local.content);
      setCopyStatus('AI 草稿已复制。');
    } catch {
      setCopyStatus('无法访问剪贴板，请在左侧草稿中手动复制。');
    }
  };

  return (
    <div className="backdrop" role="presentation">
      <section
        ref={dialog}
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <h2 id={titleId}>检测到版本冲突</h2>
        <p id={descriptionId} role="status" aria-live="assertive">
          本地草稿已安全保存。请比较两个版本，系统不会自动覆盖任一版本。
        </p>
        <div className="compare" aria-label="版本对照">
          <div>
            <b>本地草稿 · 基于 v{value.local.baseVersion}</b>
            <pre>{value.local.content}</pre>
          </div>
          <div>
            <b>服务器最新版本 · v{value.server.version}</b>
            <pre>{value.server.content}</pre>
          </div>
        </div>
        <label htmlFor={`${titleId}-resolution`}>
          手工解决草稿
          <textarea
            id={`${titleId}-resolution`}
            value={resolution}
            onChange={event => {
              setResolution(event.target.value);
              setResolutionStatus('');
            }}
          />
        </label>
        <p role="status" aria-live="polite">{resolutionStatus}</p>
        <p role="status" aria-live="polite">{copyStatus}</p>
        <div className="actions">
          <button ref={first} onClick={saveResolution}>应用手工解决并保存</button>
          <button onClick={copyLocal}>复制 AI / 本地草稿</button>
          <button onClick={onClose}>保留本地草稿并关闭</button>
          <button onClick={useServer}>丢弃本地草稿并采用服务器版本</button>
        </div>
      </section>
    </div>
  );
}
