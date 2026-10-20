// R3-I — collapsed-by-default disclosure for the Prompt adoption provenance of one shot.
//
// Nothing is fetched until the user expands it, so the Storyboard workspace read pattern and its
// exact request counts are unchanged while it is closed. The open state is bound to the
// project/document/shot/gate identity: changing any of them collapses the disclosure and discards
// the in-flight read, so a panel for a previous selection can never reappear.
import { useState } from 'react';

import { Button } from '../ui/primitives';
import { PromptAdoptionPanel } from './PromptAdoptionPanel';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

export function PromptAdoptionDisclosure({ projectId, documentId, shotId, transport, enabled,
                                               identity, read }: {
  projectId: string;
  documentId: string | null;
  shotId: string | null;
  transport: StudioGraphTransport;
  enabled: boolean;
  /** Host identity: project, branch, actor and collaboration scope. */
  identity?: string;
  /** The host's OWN read gate. Every adoption read goes through it when supplied. The signal is
      forwarded so a cancelled read is cancelled at the host too, rather than only locally. */
  read?: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
}) {
  // The open state is BOUND TO AN IDENTITY rather than reset by an effect. When any part of the
  // identity changes, `open` is already false in the SAME render - the previous selection's
  // provenance is never displayed for even one frame, and a stale expansion cannot fire a new
  // request for the new identity.
  const currentIdentity = [identity ?? '', projectId, documentId ?? '', shotId ?? '',
                           enabled ? '1' : '0'].join('\u0000');
  const [openForIdentity, setOpenForIdentity] = useState<string | null>(null);
  const [seenIdentity, setSeenIdentity] = useState<string | null>(null);

  // SYNCHRONOUS identity reset, in the render phase. An effect would leave one committed frame
  // showing the previous selection's provenance. More importantly, simply comparing
  // `openForIdentity === currentIdentity` is not enough: after A -> B -> A the stored identity
  // still equals A again, so the panel would silently RE-OPEN without the user asking. Clearing
  // the stored identity whenever the identity string changes makes the expansion a one-shot that
  // can only be re-armed by a click.
  if (seenIdentity !== currentIdentity) {
    setSeenIdentity(currentIdentity);
    setOpenForIdentity(null);
  }
  const open = openForIdentity === currentIdentity;

  const available = enabled && Boolean(documentId) && Boolean(shotId);
  return (
    <section className="prompt-adoption-disclosure">
      <Button variant="secondary" disabled={!available}
              onClick={() => setOpenForIdentity(open ? null : currentIdentity)}>
        {open ? '隐藏 Prompt 采用来源' : '查看 Prompt 采用来源'}
      </Button>
      {!available && (
        <p className="prompt-adoption-disclosure__hint">选中一个镜头后即可查看它的采用来源。</p>
      )}
      {open && available && (
        <PromptAdoptionPanel projectId={projectId} documentId={documentId} shotId={shotId}
                             transport={transport} enabled={enabled} identity={currentIdentity}
                             read={read} />
      )}
    </section>
  );
}
