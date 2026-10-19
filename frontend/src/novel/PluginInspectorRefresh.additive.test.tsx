// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api} from '../api';
import {PluginInspector} from './PluginInspector';

const inspection={id:'curated-writing-pack',name:'精选写作包',version:'1.0.0',pluginVersion:'1.0.0',status:'MANIFEST_ACTIVE',publisher:'PoemSeed',isolation:'DENY_ALL'};
const catalog=(name:string)=>({plugin_id:inspection.id,items:[{resource_id:'resources:writing.json',kind:'writing_presets',name,sha256:'a'.repeat(64),validated:true,summary:{name}}],total:1,visible:true,validated:true,validation_status:'VALIDATED',execution_supported:false,isolation:'DENY_ALL',resource_count:1,resource_kinds:['writing_presets']});
afterEach(()=>{cleanup();vi.restoreAllMocks();});

it('explicitly revalidates a loaded declarative pack, hides the old receipt while pending and never activates it',async()=>{
 let finish!:(value:ReturnType<typeof catalog>)=>void;
 const read=vi.spyOn(api,'pluginResources').mockResolvedValueOnce(catalog('原摘要')).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
 const activate=vi.spyOn(api,'enablePlugin');
 render(<PluginInspector inspection={inspection}/>);
 await screen.findByText('原摘要');
 fireEvent.click(screen.getByRole('button',{name:'重新校验资源摘要'}));
 expect(screen.queryByText('原摘要')).toBeNull();
 expect(screen.getByText('正在重新校验声明式资源…')).toBeTruthy();
 expect((screen.getByRole('button',{name:'重新校验资源摘要'}) as HTMLButtonElement).disabled).toBe(true);
 await act(async()=>finish(catalog('更新摘要')));
 expect(await screen.findByText('更新摘要')).toBeTruthy();
 expect(read).toHaveBeenCalledTimes(2);
 expect(read.mock.calls).toEqual([[inspection.id],[inspection.id]]);
 expect(activate).not.toHaveBeenCalled();
 expect(screen.getByText('PoemSeed（未验证发布者）')).toBeTruthy();
});

it.each(['version','pluginVersion'] as const)('reads the new %s of the same pack and discards a late old-version response',async field=>{
 let finish!:(value:ReturnType<typeof catalog>)=>void;
 const read=vi.spyOn(api,'pluginResources').mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce(catalog('新版摘要'));
 const view=render(<PluginInspector inspection={inspection}/>);
 view.rerender(<PluginInspector inspection={{...inspection,[field]:'2.0.0'}}/>);
 expect(await screen.findByText('新版摘要')).toBeTruthy();
 await act(async()=>finish(catalog('迟到的旧版摘要')));
 expect(screen.queryByText('迟到的旧版摘要')).toBeNull();
 expect(screen.getByText('新版摘要')).toBeTruthy();
 expect(read).toHaveBeenCalledTimes(2);
});

it('keeps the original drift boundary when an explicit revalidation fails',async()=>{
 vi.spyOn(api,'pluginResources').mockResolvedValueOnce(catalog('原摘要')).mockResolvedValueOnce({...catalog('不可展示的摘要'),validated:false,validation_status:'DRIFT',error_code:'PLUGIN_MANIFEST_DRIFT'});
 render(<PluginInspector inspection={inspection}/>);
 await screen.findByText('原摘要');
 fireEvent.click(screen.getByRole('button',{name:'重新校验资源摘要'}));
 expect(await screen.findByText('清单与已审核身份不一致，未展示声明式资源。')).toBeTruthy();
 expect(screen.queryByText('原摘要')).toBeNull();
 expect(screen.queryByText('不可展示的摘要')).toBeNull();
 expect(screen.getByRole('button',{name:'重试读取'})).toBeTruthy();
});
