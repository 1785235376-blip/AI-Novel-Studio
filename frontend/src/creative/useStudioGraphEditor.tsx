import { GraphDirectorConsole } from './GraphDirectorConsole';
import { useEffect, useRef, useState } from 'react';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { blankLocalCanvasState } from '../canvasops/canvasOps';
import type { LocalCanvasState } from '../canvasops/canvasOpsTypes';
import { StudioGraphDraftRecovery } from './StudioGraphDraftRecovery';

export type { StudioGraphEditorProps, StudioGraphEditorSelection } from './useStudioGraphEditorController';
/** Preserve the existing content/inspector consumer while separating state from rendering.
 *
 * UX-PRODUCT batch 2 (UX-04): the canvas operation rail's grouping/annotation/collapse
 * state is SESSION-LOCAL presentation only. It is never written into the saved graph and
 * is discarded whenever the captured identity changes, exactly like the controller's own
 * draft state.
 */
export function useStudioGraphEditor(props: StudioGraphEditorProps) {
  const [directorDirty, setDirectorDirty] = useState(false);
  const [directorSession, setDirectorSession] = useState(0);
  const controller = useStudioGraphEditorController({ ...props, externalDirty: props.externalDirty || directorDirty });
  const [canvasLocal, setCanvasLocal] = useState<LocalCanvasState>(() => blankLocalCanvasState());
  const identity = props.identity, identityRef = useRef(identity);
  useEffect(() => {
    if (identityRef.current !== identity) { identityRef.current = identity; setCanvasLocal(blankLocalCanvasState()); setDirectorDirty(false); }
  }, [identity]);
  const view = studioGraphEditorView(controller, { ...props, externalDirty: props.externalDirty || directorDirty }, { local: canvasLocal, onLocal: setCanvasLocal });
  return { ...view, content: <>{props.active && !controller.retired && controller.catalog && <StudioGraphDraftRecovery controller={controller} />}{props.directorSource && !controller.retired && <GraphDirectorConsole key={`${props.identity}:${directorSession}`}
    client={props.directorSource} selectionKey={JSON.stringify([controller.base?.id, controller.selected])} pin={controller.node?.definition_id === 'director_plan' ? controller.node.parameters.document_snapshot : undefined}
    graph={controller.draft} selectedNodeId={controller.node?.id}
    active={props.active && !props.denied} canMutate={props.canMutate && !props.externalDirty && !controller.executionDirty}
    busy={props.busy} isCurrent={props.isCurrent} read={props.read} mutate={props.mutate} onDirtyChange={setDirectorDirty} />}{view.content}</>,
    directorPending: directorDirty,
    dirty: directorDirty || controller.dirty || controller.blocked || controller.executionDirty,
    discard: () => { setDirectorSession(value => value + 1); setDirectorDirty(false); controller.discard(); } };

}
