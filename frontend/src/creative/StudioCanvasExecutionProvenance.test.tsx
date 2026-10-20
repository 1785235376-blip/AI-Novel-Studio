// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import fixture from '../../../tests/fixtures/studio_dual_canvas_loop.json';
import legacy from '../../../tests/fixtures/studio_canvas_return_legacy.json';
import type {ProductionJob} from './studioProductionClient';
import {projectExecution} from '../experimental/executionProvenance/executionProvenanceModel';
import {ExecutionProvenancePanel} from '../experimental/executionProvenance/ExecutionProvenancePanel';
afterEach(()=>cleanup());
const job=()=>structuredClone(fixture.approved) as unknown as ProductionJob;
it('projects only the recorded original binding and leaves old unbound Jobs unbound',()=>{
 expect(projectExecution(job()).canvasReturn).toEqual(fixture.command.canvas_return);
 expect(projectExecution(legacy.approved as unknown as ProductionJob).canvasReturn).toBeNull();
});
it.each(['project','branch','source','credential-shaped-card'])('refuses a changed persistent origin: %s',mode=>{
 const value=job(),binding=value.command!.canvas_return!;
 if(mode==='project'){binding.project_id='other-project';binding.scope.novel_id='other-project';}
 if(mode==='branch')binding.scope={mode:'collaboration',novel_id:value.novel_id,workspace_id:'workspace',storyline_id:'storyline',branch_id:'other-branch'};
 if(mode==='source'){binding.source.digest='f'.repeat(64);value.command!.source_snapshots[0].digest=binding.source.digest;value.command!.image_source!.digest=binding.source.digest;}
 if(mode==='credential-shaped-card')binding.card_id='SK_SECRET_PROBE_123456';
 expect(()=>projectExecution(value)).toThrow();
});
it('retains missing-origin and safe error-code boundaries for a legacy Job',async()=>{
 const value=structuredClone(legacy.approved) as unknown as ProductionJob;value.error_code='SK_SECRET_PROBE_123456';
 const get=vi.fn(async()=>value);render(<ExecutionProvenancePanel selection={{projectId:value.novel_id,branchId:value.branch_id,identity:'legacy',job:value}}
 production={{get}} active denied={false} isCurrent={()=>true} read={work=>work()}/>);
 expect(get).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'读取执行来源'}));
 const panel=screen.getByRole('region',{name:'执行来源与失败恢复'});await within(panel).findByText(/没有与本次任务输入匹配的会话锚点/);
 expect(panel.textContent).not.toContain('SK_SECRET_PROBE_123456');expect(panel.textContent).not.toContain('原 Job 已持久记录位置绑定');
});
