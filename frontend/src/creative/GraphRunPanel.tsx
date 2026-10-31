import { useStudioGraphRunController, type StudioGraphRunPanelProps } from './useStudioGraphRunController';
import { studioGraphRunView } from './studioGraphRunView';

export type { StudioGraphRunPanelProps } from './useStudioGraphRunController';
/** Preserve per-graph/version lifecycle while allowing a view-only UI replacement. */
export function GraphRunPanel(props: StudioGraphRunPanelProps) {
  return <ScopedGraphRunPanel key={`${props.graph?.id || 'new'}:${props.graph?.version || 0}`} {...props} />;
}
function ScopedGraphRunPanel(props: StudioGraphRunPanelProps) {
  return studioGraphRunView(useStudioGraphRunController(props), props);
}
