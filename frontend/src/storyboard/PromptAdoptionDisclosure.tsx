// R3-I — collapsed-by-default disclosure for the Prompt adoption provenance of one shot.
//
// Nothing is fetched until the user expands it, so the Storyboard workspace read pattern and its
// exact request counts are unchanged while it is closed. The open state is bound to the
// project/document/shot/gate identity: changing any of them collapses the disclosure and discards
// the in-flight read, so a panel for a previous selection can never reappear.
import { useEffect, useState } from 'react';

import { Button } from '../ui/primitives';
import { PromptAdoptionPanel } from './PromptAdoptionPanel';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

export function PromptAdoptionDisclosure({ projectId, documentId, shotId, transport, enabled }: {
  projectId: string;
  documentId: string | null;
  shotId: string | null;
  transport: StudioGraphTransport;
  enabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const identity = [projectId, documentId ?? '', shotId ?? '', enabled ? '1' : '0'].join('\u0000');

  useEffect(() => {
    // Any identity change collapses the disclosure and drops the previous selection's content.
    setOpen(false);
  }, [identity]);

  const available = enabled && Boolean(documentId) && Boolean(shotId);
  return (
    <section className="prompt-adoption-disclosure">
      <Button variant="secondary" disabled={!available}
              onClick={() => setOpen(current => !current)}>
        {open ? '隐藏 Prompt 采用来源' : '查看 Prompt 采用来源'}
      </Button>
      {!available && (
        <p className="prompt-adoption-disclosure__hint">选中一个镜头后即可查看它的采用来源。</p>
      )}
      {open && available && (
        <PromptAdoptionPanel projectId={projectId} documentId={documentId} shotId={shotId}
                             transport={transport} enabled={enabled} />
      )}
    </section>
  );
}
