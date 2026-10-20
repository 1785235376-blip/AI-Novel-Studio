import { expect, it } from 'vitest';
import { applyGraphRecipeParameters, checkedGraphRecipeParameters, graphRecipeCfgControl } from './studioGraphRecipeParameters';
import { samplingDefinition, samplingProvider } from './studioGraphRecipeParameters.testFixtures';
const provider = () => { const p = samplingProvider(); p.supported_parameters.push('cfg'); p.image_capabilities!.cfg = { min: 0, max: 12, default: 7 }; return p; };
it.each(['0','7.25','12'])('maps observed cfg %s while preserving original pins, consent, topology and other values', cfg => {
  const base = samplingDefinition(), before = structuredClone(base), p = provider();
  const edited = applyGraphRecipeParameters(base, 'generate', p, { steps: '20', seed: '7', cfg });
  expect(edited.nodes[1].parameters).toEqual({ ...before.nodes[1].parameters, parameters: { ...before.nodes[1].parameters.parameters, cfg: Number(cfg) } });
  expect(edited.edges).toBe(base.edges); expect(base).toEqual(before);
  expect(applyGraphRecipeParameters(edited, 'generate', p, { steps: '20', seed: '7', cfg: '' })).toEqual(base);
});
it.each(['12.01','-1','NaN','Infinity','1e1',' 7','7 ','0x10','true'])('rejects invalid or out-of-observation cfg %s', cfg => {
  expect(() => checkedGraphRecipeParameters({ steps: '20', seed: '7', cfg }, provider())).toThrow();
});
it.each(['legacy','cloud','flux','qwen','missing capability'] as const)('does not infer cfg authority from %s', kind => {
  const p = provider();
  if(kind==='legacy') delete p.image_capabilities!.cfg;
  if(kind==='cloud') p.local=false;
  if(kind==='flux') p.image_capabilities!.recipe_id='comfy-flux1-v1';
  if(kind==='qwen') p.image_capabilities!.recipe_id='comfy-qwen-image-v1';
  if(kind==='missing capability') p.supported_parameters=p.supported_parameters.filter(k=>k!=='cfg');
  expect(graphRecipeCfgControl(p)).toBeNull();
  expect(()=>applyGraphRecipeParameters(samplingDefinition(),'generate',p,{steps:'20',seed:'7',cfg:'7.25'})).toThrow();
});
