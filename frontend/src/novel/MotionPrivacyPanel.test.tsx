// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api} from '../api';
import {MotionPrivacyPanel} from './MotionPrivacyPanel';
afterEach(()=>{cleanup();vi.restoreAllMocks()});
it('requires visible current prompt review before approving an exact hash',async()=>{
 const record={prompt:'Synthetic camera pan',prompt_sha256:'a'.repeat(64),provider_id:'fixture',model_id:'fixture-model',privacy_level:'LOCAL_ONLY',status:'PENDING'};
 const read=vi.spyOn(api,'motionPrivacy').mockResolvedValue(record),update=vi.spyOn(api,'updateMotionPrivacy').mockResolvedValue({...record,privacy_level:'CLOUD_ALLOWED'});
 render(<MotionPrivacyPanel novelId="project-a" screenplayId="screenplay-a" taskId="task-a"/>);
 expect(update).not.toHaveBeenCalled();expect(read).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'审核云端发送内容'}));
 expect(await screen.findByText(/Synthetic camera pan/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'允许向所选云 Provider 发送此提示'}));
 await waitFor(()=>expect(update).toHaveBeenCalledWith('project-a','screenplay-a','task-a','CLOUD_ALLOWED','a'.repeat(64)));
 expect(screen.getByText(/fixture\/fixture-model/)).toBeTruthy();
});
