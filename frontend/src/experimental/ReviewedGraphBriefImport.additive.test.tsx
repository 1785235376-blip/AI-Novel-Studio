// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import wire from './reviewedGraphBrief.testFixture.json';
import {readReviewedGraphBrief} from './reviewedGraphBrief';
import {ReviewedGraphBriefImport} from './ReviewedGraphBriefImport';
import {PersonalSkillBriefComposer} from './PersonalSkillBriefComposer';
import {emptyBrief} from './personalSkillBrief';
import {createStudioGraphClient} from '../creative/studioGraphClient';
import type {StudioGraphRecord,StudioGraphRun} from '../creative/studioGraphTypes';
const graph=wire.graph as StudioGraphRecord,run=wire.run as StudioGraphRun;
const reader=()=>({get:vi.fn(async()=>structuredClone(graph)),getRun:vi.fn(async()=>structuredClone(run))});
beforeEach(()=>vi.stubGlobal('crypto',webcrypto));afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function fields(){fireEvent.change(screen.getByLabelText('简报来源运行 ID'),{target:{value:run.id}});fireEvent.change(screen.getByLabelText('简报来源审核节点 ID'),{target:{value:'review'}});}
async function inspect(){fields();fireEvent.click(screen.getByText('读取并比较原审核简报'));await screen.findByRole('region',{name:'原审核简报差异'});}
it('uses the original strict Graph client to decode actual File owner review output with pinned digest',async()=>{
 const calls=vi.fn((url:string)=>structuredClone(url.includes('/graph-runs/')?run:graph));
 const json=async <T,>(url:string):Promise<T>=>calls(url) as T;
 const client=createStudioGraphClient(run.project_id,{}, {json});const value=await readReviewedGraphBrief(client,run.id,'review');
 expect(value.text).toEqual(wire.text);expect(value.source.run_version).toBe(run.version);expect(value.source.origin).toBe('USER_SUPPLIED');expect(value.source.execution_authority).toBe(false);expect(value.source.text_sha256).toMatch(/^[a-f0-9]{64}$/);expect(calls).toHaveBeenCalledTimes(4);
});
it.each(['stale','unreviewed','failed','schema','version','node','text'])('refuses %s evidence rather than downgrading to trusted candidate',async kind=>{
 const c=reader();const r=structuredClone(run),g=structuredClone(graph);
 if(kind==='stale')r.stale=true;if(kind==='unreviewed')r.reviewed=false;if(kind==='failed')r.status='FAILED';if(kind==='schema')g.definition.schema_version=2;if(kind==='version')g.version++;if(kind==='node')g.definition.nodes.find(n=>n.id==='review')!.definition_id='draft_prepare';if(kind==='text')r.node_states.review.output!.reviewed_draft!.text='{"purpose":"x","execute":true}';
 c.get.mockResolvedValue(g);c.getRun.mockResolvedValue(r);await expect(readReviewedGraphBrief(c,run.id,'review')).rejects.toThrow();
});
it('rereads before explicit adoption and preserves current content when source changed',async()=>{
 const c=reader(),onApply=vi.fn();render(<ReviewedGraphBriefImport reader={c} active disabled={false} current={emptyBrief()} onApply={onApply}/>);await inspect();expect(onApply).not.toHaveBeenCalled();
 c.getRun.mockResolvedValue({...run,version:run.version+1});fireEvent.click(screen.getByText('重新核对来源并替换四项正文'));await screen.findByText('来源已变化，未替换正文。请重新读取并比较。');expect(onApply).not.toHaveBeenCalled();
});
it('discards pending reads across reader or inactive ABA and rejects retained callbacks',async()=>{
 const c=reader();let finish!:(r:StudioGraphRun)=>void;c.getRun.mockImplementationOnce(()=>new Promise(r=>{finish=r;}));const props={reader:c,active:true,disabled:false,current:emptyBrief(),onApply:vi.fn()};const view=render(<ReviewedGraphBriefImport {...props}/>);fields();const button=screen.getByText('读取并比较原审核简报');const callback=(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick;fireEvent.click(button);
 view.rerender(<ReviewedGraphBriefImport {...props} active={false}/>);view.rerender(<ReviewedGraphBriefImport {...props}/>);await act(async()=>finish(run));expect(screen.queryByRole('region',{name:'原审核简报差异'})).toBeNull();const calls=c.getRun.mock.calls.length;await act(async()=>callback());expect(c.getRun).toHaveBeenCalledTimes(calls);expect(props.onApply).not.toHaveBeenCalled();
});
it('keeps author/license separate and prepares only a non-executable original template package',async()=>{
 const onPrepare=vi.fn();render(<PersonalSkillBriefComposer graphReader={reader()} busy={false} onInvalidate={vi.fn()} onPrepare={onPrepare} onClose={vi.fn()}/>);
 for(const [label,value] of [['个人简报标识','personal-reviewed'],['个人简报标题','Brief'],['个人简报作者','Author'],['个人简报许可声明','Self-use']])fireEvent.change(screen.getByLabelText(label),{target:{value}});
 await inspect();fireEvent.click(screen.getByText('重新核对来源并替换四项正文'));await screen.findByText('已采用原审核文本引用，仍需填写个人身份与许可并预检安装。');expect(onPrepare).not.toHaveBeenCalled();fireEvent.click(screen.getByText('填入简报安装预览'));
 const result=JSON.parse(onPrepare.mock.calls[0][0]);expect(result.manifest.author).toBe('Author');expect(result.manifest.license).toBe('Self-use');expect(result.manifest.permissions.execute).toBe(false);expect(JSON.parse(result.manifest.provenance).run_id).toBe(run.id);expect(JSON.parse(result.manifest.provenance).publisher_verified).toBe(false);
});
it('lists original graph and completed runs without execution, then lets the user choose a review node',async()=>{
 const c={...reader(),list:vi.fn(async()=>({items:[graph,{...graph,id:'legacy',definition:{...graph.definition,schema_version:1 as const}}]})),runs:vi.fn(async()=>({items:[run,{...run,id:'pending',status:'WAITING_APPROVAL' as const,reviewed:false}]}))},onApply=vi.fn();
 render(<ReviewedGraphBriefImport reader={c} active disabled={false} current={emptyBrief()} onApply={onApply}/>);
 expect(c.list).not.toHaveBeenCalled();fireEvent.click(screen.getByText('列出本项目简报来源图'));await screen.findByLabelText('简报来源创作图');
 expect(screen.queryByRole('option',{name:/legacy/})).toBeNull();fireEvent.change(screen.getByLabelText('简报来源创作图'),{target:{value:graph.id}});fireEvent.click(screen.getByText('列出该图已完成运行'));await screen.findByLabelText('已完成的简报运行');
 expect(c.runs).toHaveBeenCalledWith(graph.id);expect(screen.queryByRole('option',{name:/pending/})).toBeNull();fireEvent.change(screen.getByLabelText('已完成的简报运行'),{target:{value:run.id}});fireEvent.change(screen.getByLabelText('已完成的文字审核节点'),{target:{value:'review'}});
 expect((screen.getByLabelText('简报来源运行 ID') as HTMLInputElement).value).toBe(run.id);expect((screen.getByLabelText('简报来源审核节点 ID') as HTMLInputElement).value).toBe('review');expect(onApply).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('读取并比较原审核简报'));await screen.findByRole('region',{name:'原审核简报差异'});expect(onApply).not.toHaveBeenCalled();
});
