// @vitest-environment jsdom
import {act,cleanup,renderHook,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {checkedStudioGraphDraft} from './studioGraphClient';
import {useStudioGraphEditorController,type StudioGraphEditorProps} from './useStudioGraphEditorController';
import {boundCatalog} from './graphBoundDraftRecovery.testFixtures';
import {templateGraph} from './workflowTaskTemplate/canvasAudioWorkflowTemplate.testFixtures';
import type {StudioClient} from './studioClient';
import type {StudioGraphSaveInput} from './studioGraphTypes';
afterEach(cleanup);
function definition(parameters:Record<string,unknown>){const graph=templateGraph();graph.definition.nodes=graph.definition.nodes.slice(0,2);graph.definition.nodes[1].parameters.parameters=parameters as never;return graph.definition;}
it.each([{gain_db:-60},{gain_db:12},{gain_db:-6.5,fade_in_ms:100,fade_out_ms:200},{gain_db:0,fade_in_ms:0,fade_out_ms:0}])('strict Graph SDK preserves real effects and omission: %j',effects=>{
 const p={in_ms:100,out_ms:900,...effects};expect(checkedStudioGraphDraft(definition(p)).nodes[1].parameters.parameters).toEqual(p);
 expect(checkedStudioGraphDraft(definition({in_ms:100,out_ms:900})).nodes[1].parameters.parameters).toEqual({in_ms:100,out_ms:900});
});
it.each([{gain_db:null},{gain_db:true},{gain_db:'-6'},{gain_db:NaN},{gain_db:Infinity},{gain_db:-60.1},{gain_db:12.1},{fade_in_ms:1.5},{fade_in_ms:-1},{fade_out_ms:true},{fade_out_ms:null},{fade_in_ms:500,fade_out_ms:301},{sample_rate:48000},{channels:2},{output_format:'FLAC'}])('strict Graph SDK refuses invalid or standalone-only controls: %j',bad=>{
 expect(()=>checkedStudioGraphDraft(definition({in_ms:100,out_ms:900,...bad}))).toThrow();
});
it('edits decimal gain and fades with original history, invalidates run intent, CAS saves and reopens; invalid combined fades cannot save',async()=>{
 let saved=templateGraph();saved.definition=definition({in_ms:100,out_ms:900});
 const saveTransport=vi.fn();
 const noExecution={createRun:vi.fn(),previewMedia:vi.fn(),dispatchMedia:vi.fn(),executeMedia:vi.fn()};
 const client={graphs:{catalog:vi.fn().mockResolvedValue(boundCatalog(3)),list:vi.fn(async()=>({items:[structuredClone(saved)]})),get:vi.fn(async()=>structuredClone(saved)),runs:vi.fn().mockResolvedValue({items:[]}),
 save:async(_id:string,input:StudioGraphSaveInput)=>{const checked=checkedStudioGraphDraft(input.definition);saveTransport(input);expect(input.expected_version).toBe(saved.version);saved={...saved,version:saved.version+1,definition:checked};return structuredClone(saved);},...noExecution}} as unknown as StudioClient;
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'audio-effects-author',client,canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work()};
 const api=renderHook(()=>useStudioGraphEditorController(props));await waitFor(()=>expect(api.result.current.editable).toBe(true));await act(()=>api.result.current.open(saved.id));act(()=>api.result.current.setSelected(['trim']));
 const original=structuredClone(api.result.current.draft),current=api.result.current.runInputCurrent;
 act(()=>api.result.current.updateMediaParameter('gain_db','-6.5'));expect(current()).toBe(false);
 act(()=>api.result.current.updateMediaParameter('fade_in_ms','100'));act(()=>api.result.current.updateMediaParameter('fade_out_ms','200'));
 expect(api.result.current.node?.parameters.parameters).toEqual({in_ms:100,out_ms:900,gain_db:-6.5,fade_in_ms:100,fade_out_ms:200});
 act(()=>api.result.current.travel(false));expect(api.result.current.node?.parameters.parameters?.fade_out_ms).toBeUndefined();act(()=>api.result.current.travel(true));
 await act(()=>api.result.current.save());expect(saveTransport).toHaveBeenCalledTimes(1);await act(()=>api.result.current.open(saved.id));act(()=>api.result.current.setSelected(['trim']));
 expect(api.result.current.node?.parameters.parameters).toEqual({in_ms:100,out_ms:900,gain_db:-6.5,fade_in_ms:100,fade_out_ms:200});expect(original.nodes[1].parameters.parameters).toEqual({in_ms:100,out_ms:900});
 act(()=>api.result.current.updateMediaParameter('fade_out_ms','701'));await act(()=>api.result.current.save());expect(saveTransport).toHaveBeenCalledTimes(1);
 act(()=>api.result.current.updateMediaParameter('fade_out_ms',''));expect(api.result.current.node?.parameters.parameters?.fade_out_ms).toBeUndefined();await act(()=>api.result.current.save());expect(saveTransport).toHaveBeenCalledTimes(2);
 Object.values(noExecution).forEach(fn=>expect(fn).not.toHaveBeenCalled());
});
