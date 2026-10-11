import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';

export type { StudioGraphEditorProps, StudioGraphEditorSelection } from './useStudioGraphEditorController';
/** Preserve the existing content/inspector consumer while separating state from rendering. */
export function useStudioGraphEditor(props: StudioGraphEditorProps) {
  const controller = useStudioGraphEditorController(props);
  return { ...studioGraphEditorView(controller, props), dirty: controller.dirty || controller.blocked || controller.executionDirty, discard: controller.discard };
}
