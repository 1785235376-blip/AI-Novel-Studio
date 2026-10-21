// @vitest-environment jsdom
import {StrictMode} from 'react';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {SavedCanvasAudioDraftPanel,type SavedCanvasAudioDraftPanelProps} from './SavedCanvasAudioDraftPanel';
import {audioDraftSummary} from './summary.testFixtures';
afterEach(cleanup);
function deferred<T>(){let resolve!:(v:T)=>void,reject!:(e:unknown)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};}
function setup(overrides:Partial<SavedCanvasAudioDraftPanelProps>={}){
 const rows=[audioDraftSummary()],resume=vi.fn(),list=vi.fn(async()=>rows),owner={project:'original',client:{}},props:SavedCanvasAudioDraftPanelProps={owner,current:true,canMutate:true,busy:false,sessionInputKey:'task-A',isCurrent:()=>true,onList:list,onResume:resume,...overrides};
 return{rows,resume,list,owner,props,...render(<SavedCanvasAudioDraftPanel {...props}/>)};
}
const button=()=>screen.getByRole('button',{name:'明确仅恢复音频输入草稿'});
async function select(){fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));await screen.findByLabelText('已保存的音频输入草稿');fireEvent.change(screen.getByLabelText('已保存的音频输入草稿'),{target:{value:'saved-audio'}});}
function consent(){fireEvent.click(screen.getByRole('checkbox',{name:'我已核对所选版本与来源，同意用已保存草稿替换当前会话输入'}));}
it('shows saved provenance and effects, then submits exactly one frozen intent only after replacement consent',async()=>{
 const f=setup();await select();expect(f.resume).not.toHaveBeenCalled();expect((button() as HTMLButtonElement).disabled).toBe(true);expect(screen.getByText(/尚未应用或保存/)).not.toBeNull();expect(screen.getByText(/截取 100–1100 ms/).textContent).toContain('-6.5 dB');expect(screen.getByText(/来源模板/).textContent).toContain('audio-template');
 consent();fireEvent.click(button());fireEvent.click(button());expect(f.resume).toHaveBeenCalledTimes(1);const copy=f.resume.mock.calls[0][0];expect(copy).toEqual(f.rows[0]);expect(copy).not.toBe(f.rows[0]);expect(Object.isFrozen(copy)).toBe(true);await screen.findByText(/已提交仅恢复输入的意图/);
});
it('works under strict effects without granting execution authority',async()=>{
 const props={owner:{project:'strict'},current:true,canMutate:true,busy:false,sessionInputKey:'A',isCurrent:()=>true,onList:vi.fn(async()=>[audioDraftSummary()]),onResume:vi.fn()};render(<StrictMode><SavedCanvasAudioDraftPanel {...props}/></StrictMode>);await select();consent();fireEvent.click(button());expect(props.onResume).toHaveBeenCalledTimes(1);
});
it('uses honest absence labels for a range-only non-derived input',async()=>{
 const row=audioDraftSummary();for(const key of ['gainDb','fadeInMs','fadeOutMs','templateGraphId','templateVersion','parentJobId','parentJobVersion'] as const)delete row[key];setup({onList:async()=>[row]});await select();expect(screen.getByText(/增益 未提供/)).not.toBeNull();expect(screen.getByText(/没有模板来源绑定/)).not.toBeNull();expect(screen.getByText(/没有失败任务派生绑定/)).not.toBeNull();
});
it('permits readonly list inspection without restore and hides an inactive owner',async()=>{
 const f=setup({canMutate:false});await select();expect((button() as HTMLButtonElement).disabled).toBe(true);expect((screen.getByRole('checkbox') as HTMLInputElement).disabled).toBe(true);expect(f.resume).not.toHaveBeenCalled();f.rerender(<SavedCanvasAudioDraftPanel {...f.props} current={false}/>);expect(screen.queryByLabelText('未入队音频草稿恢复')).toBeNull();
});
it.each(['owner','input','authority','current','busy','list callback','resume callback'] as const)('retires selection across %s A/B/A',async kind=>{
 const f=setup();await select();consent();let changed={...f.props};if(kind==='owner')changed.owner={project:'other'};if(kind==='input')changed.sessionInputKey='task-B';if(kind==='authority')changed.canMutate=false;if(kind==='current')changed.current=false;if(kind==='busy')changed.busy=true;if(kind==='list callback')changed.onList=async()=>[];if(kind==='resume callback')changed.onResume=()=>{};
 const old=button();f.rerender(<SavedCanvasAudioDraftPanel {...changed}/>);f.rerender(<SavedCanvasAudioDraftPanel {...f.props}/>);fireEvent.click(old);expect(f.resume).not.toHaveBeenCalled();expect(screen.queryByRole('checkbox')).toBeNull();
});
it.each(['owner','row','rows'] as const)('latches observed in-place %s ABA without relying on a rerender',async kind=>{
 const f=setup();await select();consent();const old=button();if(kind==='owner')f.owner.project='other';if(kind==='row')f.rows[0].gainDb=-3;if(kind==='rows')f.rows.push(audioDraftSummary('added'));
 fireEvent.click(old);if(kind==='owner')f.owner.project='original';if(kind==='row')f.rows[0].gainDb=-6.5;if(kind==='rows')f.rows.pop();fireEvent.click(old);expect(f.resume).not.toHaveBeenCalled();expect(screen.getByText(/旧恢复确认已退役/)).not.toBeNull();
});
it('does not revive a false live current getter after it later returns true',async()=>{
 let valid=true;const f=setup({isCurrent:()=>valid});await select();consent();const old=button();valid=false;fireEvent.click(old);valid=true;fireEvent.click(old);expect(f.resume).not.toHaveBeenCalled();
});
it('ignores late list results after session input ABA and unmount',async()=>{
 const pending=deferred<ReturnType<typeof audioDraftSummary>[]>(),f=setup({onList:()=>pending.promise});fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));f.rerender(<SavedCanvasAudioDraftPanel {...f.props} sessionInputKey="B"/>);f.rerender(<SavedCanvasAudioDraftPanel {...f.props}/>);await act(async()=>pending.resolve([audioDraftSummary()]));expect(screen.queryByLabelText('已保存的音频输入草稿')).toBeNull();expect(f.resume).not.toHaveBeenCalled();f.unmount();
});
it('consumes duplicate restore attempts synchronously and suppresses a late old success',async()=>{
 const pending=deferred<void>(),resume=vi.fn(()=>pending.promise),f=setup({onResume:resume});await select();consent();fireEvent.click(button());fireEvent.click(button());expect(resume).toHaveBeenCalledTimes(1);f.rerender(<SavedCanvasAudioDraftPanel {...f.props} sessionInputKey="new-input"/>);await act(async()=>pending.resolve());expect(screen.queryByText(/已提交仅恢复输入的意图/)).toBeNull();
});
it.each(['duplicate','invalid','unknown'] as const)('rejects the whole malformed %s list without displaying unknown fields',async kind=>{
 const row=audioDraftSummary(),rows=kind==='duplicate'?[row,{...row}]:[{...row,...(kind==='invalid'?{gainDb:20}:{error_code:'SYNTHETIC_SECRET_DO_NOT_SHOW'})}];setup({onList:async()=>rows});fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));await screen.findByText('音频草稿列表未能核对，请重新读取当前项目。');expect(screen.queryByLabelText('已保存的音频输入草稿')).toBeNull();expect(screen.queryByText(/SYNTHETIC_SECRET/)).toBeNull();
});
it('keeps list/restore failures generic and does not retry a consumed intent automatically',async()=>{
 const f=setup({onResume:vi.fn(async()=>{throw new Error('SYNTHETIC_SECRET_DO_NOT_SHOW');})});await select();consent();fireEvent.click(button());await screen.findByText('音频输入恢复未确认。原已保存草稿保留，请重新核对来源与版本。');expect(screen.queryByText(/SYNTHETIC_SECRET/)).toBeNull();expect((button() as HTMLButtonElement).disabled).toBe(true);expect(f.props.onResume).toHaveBeenCalledTimes(1);
});
it('shows an honest empty result and never selects by default',async()=>{setup({onList:async()=>[]});fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));await screen.findByText('没有可选择的已保存音频输入草稿。');expect(screen.queryByRole('checkbox')).toBeNull();});

it('rejects a source that changes between owned capture and live snapshot instead of restoring a mixed read',async()=>{
 const row=audioDraftSummary();let n=0;Object.defineProperty(row,'gainDb',{enumerable:true,get(){return ++n===1?-6.5:-3;}});const resume=vi.fn();setup({onList:async()=>[row],onResume:resume});fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));await screen.findByText('音频草稿列表未能核对，请重新读取当前项目。');expect(resume).not.toHaveBeenCalled();
});
it('ignores a pending list after actual unmount without submitting any recovery',async()=>{
 const pending=deferred<ReturnType<typeof audioDraftSummary>[]>(),resume=vi.fn(),f=setup({onList:()=>pending.promise,onResume:resume});fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));f.unmount();await act(async()=>pending.resolve([audioDraftSummary()]));expect(resume).not.toHaveBeenCalled();expect(screen.queryByLabelText('已保存的音频输入草稿')).toBeNull();
});
