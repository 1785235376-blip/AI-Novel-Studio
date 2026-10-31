import { useStudioGraphModelExecutionController, type StudioGraphModelExecutionPanelProps } from './useStudioGraphModelExecutionController';
import { studioGraphModelExecutionView } from './studioGraphModelExecutionView';

export type { GraphModelAction, GraphModelActionEvidence, StudioGraphModelExecutionPanelProps } from './useStudioGraphModelExecutionController';
/** Original public component; model authority remains in the headless controller. */
export function GraphModelExecutionPanel(props: StudioGraphModelExecutionPanelProps) {
  return studioGraphModelExecutionView(useStudioGraphModelExecutionController(props), props);
}
