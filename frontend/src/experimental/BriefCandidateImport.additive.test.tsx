// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {parseBriefModelCandidate,briefModelPrompt} from './briefModelCandidate';
import {BriefCandidateImport} from './BriefCandidateImport';
import {PersonalSkillBriefComposer} from './PersonalSkillBriefComposer';
import {emptyBrief} from './personalSkillBrief';
import {buildGraphStarter} from '../creative/graphStarter';
import {blankGraph} from '../creative/graphDraft';
import {modelCatalog} from '../creative/studioGraphModel.testFixtures';
const value={purpose:'用途',writing_goals:'目标',constraints:'不增加许可',checklist:'人工确认'},text=JSON.stringify(value);
afterEach(cleanup);
const click=(name:string)=>fireEvent.click(screen.getByText(name));
const fill=()=>{fireEvent.change(screen.getByLabelText('待审核简报 JSON'),{target:{value:text}});click('比较四项简报内容');};
it('builds ordinary text/model/review nodes without route selection or new execution owner',()=>{
 const draft={...blankGraph(),schema_version:2 as const};const graph=buildGraphStarter(draft,modelCatalog(),'brief-model','Keep this constraint.');
 expect(graph.nodes.map(n=>n.definition_id)).toEqual(['text_input','text_generate','human_review']);
 expect(graph.nodes[0].parameters.text).toContain('Keep this constraint.');expect(graph.nodes[1].parameters.instruction).toContain('checklist');
 expect(draft.nodes).toHaveLength(0);expect(()=>buildGraphStarter(draft,modelCatalog(false),'brief-model','x')).toThrow();
 expect(()=>briefModelPrompt('x'.repeat(6001))).toThrow();
});
it('accepts exactly four declarative strings, rejecting duplicate escaped keys and authority fields',()=>{
 expect(parseBriefModelCandidate(text)).toEqual(value);
 for(const bad of [text.slice(0,-1)+',"purpose":"duplicate"}',text.slice(0,-1)+',"\\u0070urpose":"duplicate"}',text.slice(0,-1)+',"license":"mine"}',JSON.stringify({...value,checklist:[]}),text+' trailing',text.slice(0,-1)+',}',JSON.stringify({...value,purpose:'x'.repeat(8001)})])expect(()=>parseBriefModelCandidate(bad)).toThrow();
});
it('requires visible comparison and retires stale approval across edits, IME and inactive ABA',()=>{
 const p={active:true,disabled:false,current:emptyBrief(),onApply:vi.fn()};const v=render(<BriefCandidateImport {...p}/>);fill();
 const b=screen.getByText('确认替换四项正文');const old=(b as any)[Object.keys(b).find(k=>k.startsWith('__reactProps$'))!].onClick;
 v.rerender(<BriefCandidateImport {...p} active={false}/>);v.rerender(<BriefCandidateImport {...p}/>);act(()=>old());expect(p.onApply).not.toHaveBeenCalled();
 fill();fireEvent.compositionStart(screen.getByLabelText('待审核简报 JSON'));expect(screen.queryByText('确认替换四项正文')).toBeNull();fireEvent.compositionEnd(screen.getByLabelText('待审核简报 JSON'));
 click('比较四项简报内容');click('确认替换四项正文');expect(p.onApply).toHaveBeenCalledTimes(1);expect(p.onApply).toHaveBeenCalledWith(value);
});
it('preserves identity/license and uses original preview preparation with unverified provenance',()=>{
 const p={busy:false,onPrepare:vi.fn(),onInvalidate:vi.fn(),onClose:vi.fn()};render(<PersonalSkillBriefComposer {...p}/>);
 for(const [label,val] of [['个人简报标识','personal-candidate'],['个人简报标题','My brief'],['个人简报作者','Author'],['个人简报许可声明','Self-use only']])fireEvent.change(screen.getByLabelText(label),{target:{value:val}});
 fill();expect(p.onPrepare).not.toHaveBeenCalled();click('确认替换四项正文');expect((screen.getByLabelText('简报用途') as HTMLTextAreaElement).value).toBe(value.purpose);
 expect((screen.getByLabelText('个人简报许可声明') as HTMLInputElement).value).toBe('Self-use only');click('填入简报安装预览');
 const result=JSON.parse(p.onPrepare.mock.calls[0][0]);expect(result.manifest.provenance).toBe('PERSONAL_USER_SUPPLIED_MODEL_CANDIDATE_UNVERIFIED');expect(result.manifest.permissions.execute).toBe(false);
});
