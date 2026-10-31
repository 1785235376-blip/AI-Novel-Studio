// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {InboxPanel} from './InboxPanel';
import {ApiError} from '../api';
import type {ExperimentalClient} from './api';
afterEach(cleanup);
const row={id:'original-finding-id',domain:'continuity_finding',version:2,status:'REVIEW_REQUIRED',stale:true,preview:'Synthetic finding for original source',source_hash:'a'.repeat(64),source_versions:{'n:1':{version:3,digest:'b'.repeat(64)}},allowed_actions:[],batch_safe:false,target:{panel:'check',finding_id:'original-finding-id',review_version:2,navigation_contract:'FORMAL_TARGET_ONLY',source_navigation:{chapter_id:'n:1',chapter_version:3,exact:true}}};
it('filters original finding/Canon domains and honestly presents formal navigation metadata without generic approval',async()=>{
 const get=vi.fn().mockResolvedValue({items:[row]});const post=vi.fn();render(<InboxPanel client={{get,post} as unknown as ExperimentalClient}/>);
 await screen.findByRole('article',{name:'审核项 continuity_finding Synthetic finding for original source'});
 for(const domain of ['continuity_finding','narrative_finding','pending_canon'])expect(screen.getByRole('option',{name:domain})).toBeTruthy();
 expect(screen.getByText(/目标信息仅为导航契约/)).toBeTruthy();expect(screen.queryByRole('button',{name:'批准此审核项'})).toBeNull();expect(screen.queryByLabelText('加入安全批量审核')).toBeNull();
 expect((screen.getByRole('button',{name:'批量批准已选审核项'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('审核领域'),{target:{value:'pending_canon'}});fireEvent.click(screen.getByRole('button',{name:'筛选审核项'}));
 await waitFor(()=>expect(get).toHaveBeenCalledWith('/review-inbox?domain=pending_canon',expect.any(AbortSignal)));expect(post).not.toHaveBeenCalled();
});
it('withholds cached original review metadata when refreshed authority is denied',async()=>{
 const get=vi.fn().mockResolvedValueOnce({items:[row]}).mockRejectedValue(new ApiError({status:403,code:'FORBIDDEN',message:'Current scope denied'}));
 render(<InboxPanel client={{get,post:vi.fn()} as unknown as ExperimentalClient}/>);await screen.findByText(row.preview);
 fireEvent.click(screen.getByRole('button',{name:'刷新实验记录'}));await screen.findByRole('alert');expect(screen.queryByText(row.preview)).toBeNull();expect(screen.queryByRole('article')).toBeNull();
});
