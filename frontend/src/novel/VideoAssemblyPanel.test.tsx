// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api} from '../api';
import {VideoAssemblyPanel} from './VideoAssemblyPanel';
afterEach(()=>{cleanup();vi.restoreAllMocks()});
it('submits explicit clip order and trims without claiming an audio mix',async()=>{
 vi.spyOn(api,'assets').mockResolvedValue([{id:'asset-a',filename:'clip-a.mp4'}] as any);
 vi.spyOn(api,'videoAssemblies').mockResolvedValue({items:[]});
 const create=vi.spyOn(api,'createVideoAssembly').mockResolvedValue({id:'assembly-a',status:'SUCCEEDED'});
 render(<VideoAssemblyPanel novelId="project-a" screenplayId="screenplay-a"/>);
 await waitFor(()=>expect((screen.getByRole('button',{name:'添加片段'}) as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(screen.getByRole('button',{name:'添加片段'}));
 fireEvent.change(screen.getByLabelText('起点（毫秒）'),{target:{value:'200'}});fireEvent.change(screen.getByLabelText('终点（留空使用原时长）'),{target:{value:'900'}});
 fireEvent.click(screen.getByRole('button',{name:'生成无声审核片'}));
 await waitFor(()=>expect(create).toHaveBeenCalledWith('project-a','screenplay-a',[{asset_id:'asset-a',start_ms:200,end_ms:900}]));
 expect(screen.getByText(/音轨不会合入/)).toBeTruthy();
});
