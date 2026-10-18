import {modelCenterCatalog} from './modelCenterContract';
// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import wire from './bailianPresetWire.testFixture.json';
import {checkedBailianPresets,bailianHostPreview} from './bailianPresetContract';
import {BailianPresetPanel} from './BailianPresetPanel';
import {ModelCenterPanel} from './ModelCenterPanel';
import type {StudioGraphTransport} from '../creative/studioGraphClient';
import {createModelCenterClient} from './modelCenterClient';
const endpoint='/api/model-center/provider-presets/bailian-text';
function setup(){const calls=vi.fn(async(url:string,method:string)=>{if(url!==endpoint||method!=='GET')throw new Error('No other operation permitted');return structuredClone(wire);});const transport={json:calls} as unknown as StudioGraphTransport;return {calls,props:{projectId:'project',transport,identity:'scope',active:true,denied:false,busy:false,isCurrent:()=>true,read:async<T,>(work:()=>Promise<T>)=>work()}};}
afterEach(cleanup);
it('decodes genuine route constants and refuses foreign regions, URLs, secrets and command injection',()=>{
 const catalog=checkedBailianPresets(wire);expect(bailianHostPreview(catalog,'cn-beijing','user-selected-model')).toBe('ALIYUN_BAILIAN_REGION=cn-beijing\nALIYUN_BAILIAN_MODEL=user-selected-model');
 for(const model of ['','model\nOTHER=value','model;run','$(run)','model with spaces'])expect(bailianHostPreview(catalog,'cn-beijing',model)).toBeUndefined();
 for(const mutate of [(v:typeof wire)=>{v.regions[0].base_url='https://untrusted.invalid/';},(v:typeof wire)=>{v.credential_value_included=true;},(v:typeof wire)=>{v.regions[1].id=v.regions[0].id;}]){const value=structuredClone(wire);mutate(value);expect(()=>checkedBailianPresets(value)).toThrow();}
});
it('reads only explicitly and prepares local non-secret text without applying anything',async()=>{
 const {calls,props}=setup();render(<BailianPresetPanel {...props}/>);expect(calls).not.toHaveBeenCalled();fireEvent.click(screen.getByText('明确读取百炼文本预设'));await screen.findByLabelText('百炼 API 地区');fireEvent.change(screen.getByLabelText('百炼 API 地区'),{target:{value:'cn-hongkong'}});fireEvent.change(screen.getByLabelText('百炼文本模型 ID'),{target:{value:'selected-model'}});expect((screen.getByLabelText('手动主机配置预览（未应用）') as HTMLTextAreaElement).value).toContain('ALIYUN_BAILIAN_REGION=cn-hongkong');expect(calls).toHaveBeenCalledTimes(1);expect(screen.queryByLabelText(/密钥/)).toBeNull();
});
it('retires late catalog and input on identity changes, with no silent retry',async()=>{
 const {props}=setup();let finish!:(v:unknown)=>void;let signal:AbortSignal|undefined;const transport={json:vi.fn((_url:string,_method:string,_body:unknown,s?:AbortSignal)=>{signal=s;return new Promise(r=>{finish=r;});})} as unknown as StudioGraphTransport;const view=render(<BailianPresetPanel {...props} transport={transport}/>);fireEvent.click(screen.getByText('明确读取百炼文本预设'));view.rerender(<BailianPresetPanel {...props} transport={transport} identity="other"/>);expect(signal?.aborted).toBe(true);await act(async()=>finish(wire));expect(screen.queryByLabelText('百炼 API 地区')).toBeNull();
});
it('mounts in the existing model center without adding automatic calls and denies foreign project scope',async()=>{
 const {calls,props}=setup();render(<ModelCenterPanel {...props} mutate={work=>work()} catalog={modelCenterCatalog({items:[]},{items:[]})}/>);expect(calls.mock.calls.some(([url])=>url===endpoint)).toBe(false);fireEvent.click(screen.getByText('明确读取百炼文本预设'));await screen.findByLabelText('百炼 API 地区');expect(calls.mock.calls.filter(([url])=>url===endpoint)).toHaveLength(1);
 const other=createModelCenterClient('project',props.transport,{projectId:'other'} as never);await expect(other.bailianPresets()).rejects.toThrow();expect(calls.mock.calls.filter(([url])=>url===endpoint)).toHaveLength(1);
});

it('leaves preset reads disabled for invalid project context without crashing the panel',()=>{
 const {calls,props}=setup();render(<BailianPresetPanel {...props} projectId=""/>);expect(screen.getByText('当前项目上下文无效，预设读取已停用。')).toBeTruthy();fireEvent.click(screen.getByText('明确读取百炼文本预设'));expect(calls).not.toHaveBeenCalled();
});
