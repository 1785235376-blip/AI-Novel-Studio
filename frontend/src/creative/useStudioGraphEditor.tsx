import { useEffect, useRef, useState } from 'react';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { blankLocalCanvasState } from '../canvasops/canvasOps';
import type { LocalCanvasState } from '../canvasops/canvasOpsTypes';

export type { StudioGraphEditorProps, StudioGraphEditorSelection } from './useStudioGraphEditorController';
/** Preserve the existing content/inspector consumer while separating state from rendering.
 *
 * UX-PRODUCT batch 2 (UX-04): the canvas operation rail's grouping/annotation/collapse
 * state is SESSION-LOCAL presentation only. It is never written into the saved graph and
 * is discarded whenever the captured identity changes, exactly like the controller's own
 * draft state.
 */
export function useStudioGraphEditor(props: StudioGraphEditorProps) {
  const controller = useStudioGraphEditorController(props);
  const [canvasLocal, setCanvasLocal] = useState<LocalCanvasState>(() => blankLocalCanvasState());
  const identity = props.identity, identityRef = useRef(identity);
  useEffect(() => {
    if (identityRef.current !== identity) { identityRef.current = identity; setCanvasLocal(blankLocalCanvasState()); }
  }, [identity]);
  return { ...studioGraphEditorView(controller, props, { local: canvasLocal, onLocal: setCanvasLocal }),
    dirty: controller.dirty || controller.blocked || controller.executionDirty, discard: controller.discard };
}
