import {expect,it} from 'vitest';
import {exportTextGraphTemplate,planTextGraphTemplate} from './graphTextTemplates';
import {templateCapacitySource,templateCapacityTarget} from './graphTextTemplateCapacity.testFixtures';
import {graphNoteDefinitionBytes} from './graphCanvasNotesHelpers';
import {modelCatalog} from './studioGraphModel.testFixtures';
it('rejects the independently reproduced JS-admitted/Python-rejected visual append atomically',()=>{
 const target=templateCapacityTarget(31223),before=structuredClone(target),raw=exportTextGraphTemplate(templateCapacitySource());
 expect(()=>planTextGraphTemplate(raw,target,modelCatalog())).toThrow('模板追加将超过原图定义大小限制。');expect(target).toEqual(before);
});
it('admits the adjacent valid control through the original conservative whole-graph estimate',()=>{
 const target=templateCapacityTarget(31207),before=structuredClone(target),plan=planTextGraphTemplate(exportTextGraphTemplate(templateCapacitySource()),target,modelCatalog());
 expect(new TextEncoder().encode(JSON.stringify(plan.result.definition)).length).toBe(95950);expect(graphNoteDefinitionBytes(plan.result.definition)).toBe(95998);expect(plan.result.definition.presentation?.notes).toHaveLength(1);expect(target).toEqual(before);
});
