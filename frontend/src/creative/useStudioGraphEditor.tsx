import { MediaCanvasViewPanel } from './MediaCanvasViewPanel';
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
  const imageSelectionLock = useRef(false);
  const [directorDirty, setDirectorDirty] = useState(false);
  const [mediaViewDirty, setMediaViewDirty] = useState(false);
  const [directorSession, setDirectorSession] = useState(0);
  const controller = useStudioGraphEditorController({ ...props, isDirectorImagePending: () => imageSelectionLock.current, externalDirty: props.externalDirty || directorDirty || mediaViewDirty });
  const [canvasLocal, setCanvasLocal] = useState<LocalCanvasState>(() => blankLocalCanvasState());
  const identity = props.identity, identityRef = useRef(identity);
  useEffect(() => {
    if (identityRef.current !== identity) { identityRef.current = identity; setCanvasLocal(blankLocalCanvasState()); setDirectorDirty(false); setMediaViewDirty(false); }
  }, [identity]);
  const handoffKey = JSON.stringify([props.active, props.denied, controller.executionDirty, controller.base?.id, controller.base?.version, controller.selected, controller.draft]);
  const handoffAuthority = useRef({ key: handoffKey, epoch: 0 });
  if (handoffAuthority.current.key !== handoffKey) handoffAuthority.current = { key: handoffKey, epoch: handoffAuthority.current.epoch + 1 };
  const handoffEpoch = handoffAuthority.current.epoch;
  const view = studioGraphEditorView(controller, { ...props, externalDirty: props.externalDirty || directorDirty || mediaViewDirty }, { local: canvasLocal, onLocal: setCanvasLocal });
  return { ...view, content: <>{!controller.retired && props.client.graphs?.canvasViews && <MediaCanvasViewPanel key={`media:${props.identity}:${directorSession}`} {...props} externalDirty={props.externalDirty || directorDirty || controller.dirty || controller.blocked || controller.executionDirty} onDirtyChange={setMediaViewDirty} graphHandoff={controller.canvasAssetHandoff} />}{props.active && !controller.retired && controller.catalog && <StudioGraphDraftRecovery controller={controller} />}{props.directorSource && !controller.retired && <GraphDirectorConsole key={`${props.identity}:${directorSession}`}
    client={props.directorSource} onOpenStoryboard={controller.executionDirty || !props.onOpenStoryboard ? undefined : (request, isOriginCurrent) => {
      props.onOpenStoryboard!(request, () => isOriginCurrent() && handoffAuthority.current.epoch === handoffEpoch);
    }} onOpenModels={props.onOpenModels} onOpenBroker={props.onOpenBroker} selectionKey={JSON.stringify([controller.base?.id, controller.selected, handoffEpoch])} canvasHandoff={controller.reviewedDirectorHandoff} pin={controller.node?.definition_id === 'director_plan' ? controller.node.parameters.document_snapshot : undefined}
    graph={controller.draft} selectedNodeId={controller.node?.id}
    active={props.active && !props.denied} canMutate={props.canMutate && !props.externalDirty && !mediaViewDirty && !controller.executionDirty}
    busy={props.busy} isCurrent={props.isCurrent} read={props.read} mutate={props.mutate} onDirtyChange={setDirectorDirty} onImagePendingChange={value => { imageSelectionLock.current = value; }} />}{view.content}</>,
    directorPending: directorDirty,
    dirty: mediaViewDirty || directorDirty || controller.dirty || controller.blocked || controller.executionDirty,
    discard: () => { imageSelectionLock.current = false; setDirectorSession(value => value + 1); setDirectorDirty(false); setMediaViewDirty(false); controller.discard(); } };

}
