// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { graphDraftChecklist } from './graphDraftChecklistHelpers';
import { GraphDraftChecklist } from './GraphDraftChecklist';
import { blankGraph } from './graphDraft';
import { buildGraphStarter } from './graphStarter';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import type { StudioGraphCatalog } from './studioGraphTypes';
import imageJson from './fixtures/imageGraph.catalog.json';
afterEach(cleanup);
const imageCatalog=imageJson as unknown as StudioGraphCatalog;
const imageDraft=()=>buildGraphStarter({...blankGraph(),schema_version:4},imageCatalog,'image-draft','Private source text');
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
it('uses original contract verdict and points out provider/model without leaking authored text',()=>{
 const draft=imageDraft(),before=structuredClone(draft),result=graphDraftChecklist(draft,imageCatalog.definitions);
 expect(result.contractValid).toBe(false);expect(result.hints.filter(row=>row.kind==='configuration')).toHaveLength(2);expect(JSON.stringify(result)).not.toContain('Private source text');expect(draft).toEqual(before);
 draft.nodes[2].parameters.provider_id='fixture-provider';draft.nodes[2].parameters.model_id='fixture-model';expect(graphDraftChecklist(draft,imageCatalog.definitions).contractValid).toBe(true);
});
it('distinguishes savable disconnected inputs from execution readiness and skips disabled input guidance',()=>{
 const draft=modelGraph().definition;draft.edges=[];const result=graphDraftChecklist(draft,modelCatalog().definitions);
 expect(result.contractValid).toBe(true);expect(result.hints.filter(row=>row.kind==='execution')).toHaveLength(2);
 draft.nodes.forEach(node=>{node.enabled=false;});expect(graphDraftChecklist(draft,modelCatalog().definitions).hints).toHaveLength(0);
});
it('keeps disabled incomplete configuration visible because original save validates it',()=>{
 const draft=imageDraft();draft.nodes[2].enabled=false;expect(graphDraftChecklist(draft,imageCatalog.definitions).hints.filter(row=>row.kind==='configuration')).toHaveLength(2);
});
it('reports typed connection problems using original connection checker',()=>{
 const draft=modelGraph().definition;draft.edges[0].source_port='unknown';const result=graphDraftChecklist(draft,modelCatalog().definitions);
 expect(result.contractValid).toBe(false);expect(result.hints.some(row=>row.kind==='connection'&&row.nodeId==='generate')).toBe(true);
});
it('only selects an original node and retires old callbacks after scope changes',()=>{
 const props={draft:imageDraft(),catalog:imageCatalog.definitions,scope:{},disabled:false,onSelect:vi.fn()};const view=render(<GraphDraftChecklist {...props}/>);
 const buttons=screen.getAllByRole('button',{name:/定位节点/,hidden:true});const callback=handler(buttons[0]);fireEvent.click(buttons[0]);expect(props.onSelect).toHaveBeenCalledWith([props.draft.nodes[2].id]);
 props.onSelect.mockClear();view.rerender(<GraphDraftChecklist {...props} scope={{}}/>);act(()=>callback());expect(props.onSelect).not.toHaveBeenCalled();
});
it('bounds visible guidance pages and never marks its result as execution authorization',()=>{
 const draft=modelGraph().definition;draft.edges=[];draft.nodes=Array.from({length:24},(_,i)=>({...draft.nodes[1],id:`node_${i}`}));
 render(<GraphDraftChecklist draft={draft} catalog={modelCatalog().definitions} scope={{}} disabled={false} onSelect={vi.fn()}/>);
 expect(screen.getAllByRole('button',{name:/定位节点/,hidden:true})).toHaveLength(20);fireEvent.click(screen.getByRole('button',{name:'下一页配置提示',hidden:true}));expect(screen.getAllByRole('button',{name:/定位节点/,hidden:true})).toHaveLength(4);
 expect(screen.getByText(/来源权限、版本、预算/)).toBeTruthy();
});
