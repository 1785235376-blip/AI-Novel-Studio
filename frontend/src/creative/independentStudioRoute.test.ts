// [HERMIA-FE-20261031 ACT] Reproduce-first: an activated (NEUTRAL_STUDIO) project auto-entering IMAGE must land on the
// image page (formal canvas node flow), not the legacy independent workbench, unless an asset was explicitly sent.
import { expect, it } from 'vitest';
import { routesToIndependentStudio } from './independentStudioRoute';
const base = { independentStudios: true, neutralStudio: true, currentStudioRequest: true, requestedAssetId: undefined as string | undefined };
it('activated IMAGE auto-entry without an explicit asset goes to the image page', () => {
  expect(routesToIndependentStudio({ ...base, module: 'IMAGE' })).toBe(false);
});
it('explicit asset sent to IMAGE still opens the independent workbench', () => {
  expect(routesToIndependentStudio({ ...base, module: 'IMAGE', requestedAssetId: 'asset-1' })).toBe(true);
});
it('other manual modules keep the independent workbench for activated projects', () => {
  for (const module of ['ASSETS', 'VIDEO', 'AUDIO', 'EDIT'] as const) expect(routesToIndependentStudio({ ...base, currentStudioRequest: false, module })).toBe(true);
  expect(routesToIndependentStudio({ ...base, neutralStudio: false, currentStudioRequest: false, module: 'VIDEO' })).toBe(false);
  expect(routesToIndependentStudio({ ...base, module: 'NOVEL' })).toBe(false);
  expect(routesToIndependentStudio({ ...base, independentStudios: false, module: 'VIDEO' })).toBe(false);
});
