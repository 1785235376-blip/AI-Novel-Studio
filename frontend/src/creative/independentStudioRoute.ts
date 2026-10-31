// [HERMIA-FE-20261031 ACT] Which shell renders a manual studio module. IMAGE always uses the image page (formal canvas
// node flow) unless an asset was explicitly sent to the legacy independent workbench.
import type { StudioModule } from '../ui/AppShell';

export function routesToIndependentStudio(input: {
  independentStudios: boolean; neutralStudio: boolean; currentStudioRequest: boolean; requestedAssetId?: string; module: StudioModule;
}): boolean {
  const { independentStudios, neutralStudio, currentStudioRequest, requestedAssetId, module } = input;
  if (!independentStudios || !['IMAGE', 'ASSETS', 'VIDEO', 'AUDIO', 'EDIT'].includes(module)) return false;
  if (module === 'IMAGE') return currentStudioRequest && !!requestedAssetId;
  return currentStudioRequest || neutralStudio;
}
