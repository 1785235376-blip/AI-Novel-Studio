// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {GraphTextTemplateTools} from './GraphTextTemplateTools';
import {useStudioGraphEditorController,type StudioGraphEditorController,type StudioGraphEditorProps} from './useStudioGraphEditorController';
import {templateCapacitySource,templateCapacityTarget} from './graphTextTemplateCapacity.testFixtures';
import {exportTextGraphTemplate} from './graphTextTemplates';
import {modelCatalog} from './studioGraphModel.testFixtures';
afterEach(cleanup);
it('refuses canonical overflow before confirmation and leaves original draft and history unchanged',async()=>{
 let control!:StudioGraphEditorController;const save=vi.fn(),run=vi.fn();const props:StudioGraphEditorProps={active:true,denied:false,identity:'capacity:actor',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),client:{graphs:{catalog:async()=>modelCatalog(),list:async()=>({items:[]}),create:save,createRun:run}} as any};
 function Mounted(){const c=useStudioGraphEditorController(props);control=c;return c.catalog?<GraphTextTemplateTools definition={c.draft} catalog={c.catalog} owner={c.insertionScope} disabled={!c.editable} isCurrent={c.current} onApply={(d,ids)=>{c.change(d);c.setSelected(ids)}}/>:null}
 render(<Mounted/>);await waitFor(()=>expect(control.editable).toBe(true));const target=templateCapacityTarget(31223);act(()=>control.change(target));const past=structuredClone(control.past),future=structuredClone(control.future),raw=exportTextGraphTemplate(templateCapacitySource());
 fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'),{target:{files:[{size:new TextEncoder().encode(raw).length,text:async()=>raw}]}});await screen.findByText(/模板读取或兼容性检查失败/);
 expect(screen.queryByText('明确追加模板节点')).toBeNull();expect(control.draft).toBe(target);expect(control.past).toEqual(past);expect(control.future).toEqual(future);expect(save).not.toHaveBeenCalled();expect(run).not.toHaveBeenCalled();
});
