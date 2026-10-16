// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {PendingCanonReviewPanel} from './PendingCanonReviewPanel';
import {ApiError} from '../api';
import {useStudio} from '../store';
const mocks=vi.hoisted(()=>({flags:vi.fn(),list:vi.fn(),preview:vi.fn(),review:vi.fn(),recover:vi.fn(),cancelRecovery:vi.fn()}));
vi.mock('../experimental/api',()=>({experimentalFeatures:mocks.flags}));
vi.mock('./pendingCanonReviewClient',()=>({pendingCanonReviewClient:()=>mocks}));
const row={id:'pending',version:1,status:'PENDING',preview_digest:'a'.repeat(64),proposals:[{fact:'Synthetic sealed door'}],source:{chapter_id:'n:1',version:1,digest:'b'.repeat(64)},source_evidence:{chapter_id:'n:1',version:1,content:'Exact synthetic source'},source_state:'EXPLICIT_CURRENT_SOURCE',lineage:'LEGACY_SOURCE_VERSION_NOT_RECORDED',history:[],recovery_required:false,allowed_actions:['approve','reject'],stale_source:false};
function show(){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});return render(<QueryClientProvider client={client}><PendingCanonReviewPanel projectId="n" chapterId="n:1"/></QueryClientProvider>)}
async function open(){fireEvent.click(await screen.findByRole('button',{name:'查看 Canon 候选与历史'}));await screen.findByRole('region',{name:'Canon 人工确认'});}
function confirm(){fireEvent.change(screen.getByLabelText('Canon 审阅理由'),{target:{value:'Checked every candidate and source'}});fireEvent.click(screen.getByLabelText('已核对全部候选事实与来源'));}
beforeEach(()=>{vi.resetAllMocks();mocks.flags.mockResolvedValue({features:{'experimental.finding_review_v1':true}});mocks.list.mockResolvedValue({items:[row]});mocks.preview.mockResolvedValue(row);mocks.review.mockResolvedValue({...row,version:2,status:'APPROVED',allowed_actions:[],history:[{version:1,action:'APPROVE',actor_id:'author',reason:'Checked every candidate and source'}]});mocks.recover.mockResolvedValue({...row,status:'APPROVED',allowed_actions:[]});mocks.cancelRecovery.mockResolvedValue({...row,version:2});useStudio.setState({sessionToken:'',scope:undefined,actor:undefined});});
afterEach(cleanup);
describe('original Canon review surface',()=>{
  it('requires human review, closes without write, and deduplicates clicks with exact CAS evidence',async()=>{
    show();await open();expect(screen.getByDisplayValue('Exact synthetic source')).toBeTruthy();expect(mocks.preview).toHaveBeenCalledWith('pending',undefined);
    expect((screen.getByRole('button',{name:'确认批准 Canon'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'关闭 Canon 审阅'}));expect(mocks.review).not.toHaveBeenCalled();
    await open();confirm();fireEvent.click(screen.getByRole('button',{name:'确认批准 Canon'}));fireEvent.click(screen.getByRole('button',{name:'确认批准 Canon'}));
    await waitFor(()=>expect(mocks.review).toHaveBeenCalledTimes(1));
    expect(mocks.review).toHaveBeenCalledWith('pending',expect.objectContaining({expected_version:1,preview_digest:row.preview_digest,chapter_id:'n:1',action:'approve',confirmed:true}));
    await screen.findByText('候选 v2 · APPROVED');expect(screen.queryByRole('button',{name:'确认批准 Canon'})).toBeNull();
  });
  it('invalidates approval after changing the explicit source until previewed again',async()=>{
    show();await open();confirm();fireEvent.change(screen.getByLabelText('Canon 来源章节 ID'),{target:{value:'n:2'}});fireEvent.click(screen.getByLabelText('已核对全部候选事实与来源'));
    expect((screen.getByRole('button',{name:'确认批准 Canon'}) as HTMLButtonElement).disabled).toBe(true);
    mocks.preview.mockResolvedValue({...row,source:{...row.source,chapter_id:'n:2'},preview_digest:'c'.repeat(64)});
    fireEvent.click(screen.getByRole('button',{name:'重新预览 Canon 来源'}));await screen.findByText('已核对来源 n:2 · v1');
    expect((screen.getByRole('button',{name:'确认批准 Canon'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已核对全部候选事实与来源'));fireEvent.click(screen.getByRole('button',{name:'确认批准 Canon'}));
    await waitFor(()=>expect(mocks.review).toHaveBeenCalledWith('pending',expect.objectContaining({chapter_id:'n:2',preview_digest:'c'.repeat(64)})));
  });
  it('retains reasons on conflict without retrying or silently refreshing approval',async()=>{
    mocks.review.mockRejectedValue(new ApiError({status:409,code:'CANON_PREVIEW_STALE',message:'Source changed. Preview again.'}));show();await open();confirm();fireEvent.click(screen.getByRole('button',{name:'确认批准 Canon'}));
    await screen.findByRole('alert');expect(screen.getByDisplayValue('Checked every candidate and source')).toBeTruthy();expect(mocks.review).toHaveBeenCalledTimes(1);
  });
  it('offers recovery and cancellation only for prepared receipts',async()=>{
    mocks.list.mockResolvedValue({items:[{...row,recovery_required:true,allowed_actions:['recover','cancel_recovery']}]});show();
    fireEvent.click(await screen.findByRole('button',{name:'恢复 Canon 提交凭据'}));await waitFor(()=>expect(mocks.recover).toHaveBeenCalledWith('pending',1));
    fireEvent.click(screen.getByRole('button',{name:'取消尚未提交的 Canon 操作'}));await waitFor(()=>expect(mocks.cancelRecovery).toHaveBeenCalledWith('pending',1));expect(mocks.review).not.toHaveBeenCalled();
  });
  it('withholds cached proposals and source when permission is revoked',async()=>{
    mocks.review.mockRejectedValue(new ApiError({status:403,code:'FORBIDDEN',message:'Project review permission required'}));show();await open();confirm();fireEvent.click(screen.getByRole('button',{name:'确认批准 Canon'}));
    await screen.findByRole('alert');expect(screen.queryByText(/Synthetic sealed door/)).toBeNull();expect(screen.queryByDisplayValue('Exact synthetic source')).toBeNull();
  });
  it('discards late preview after scope navigation',async()=>{
    let resolve!:(value:unknown)=>void;mocks.preview.mockReturnValue(new Promise(r=>{resolve=r}));show();fireEvent.click(await screen.findByRole('button',{name:'查看 Canon 候选与历史'}));
    act(()=>useStudio.setState({sessionToken:'new-identity'}));await act(async()=>resolve(row));expect(screen.queryByDisplayValue('Exact synthetic source')).toBeNull();
  });
  it('shows missing configuration, empty and disabled states honestly',async()=>{
    mocks.preview.mockResolvedValue({...row,source:null,source_evidence:null,source_state:'NOT_CONFIGURED',allowed_actions:['reject']});const view=show();await open();confirm();expect((screen.getByRole('button',{name:'确认批准 Canon'}) as HTMLButtonElement).disabled).toBe(true);view.unmount();
    mocks.list.mockResolvedValue({items:[]});const empty=show();await screen.findByText('没有 Canon 候选');empty.unmount();mocks.flags.mockResolvedValue({features:{'experimental.finding_review_v1':false}});show();await screen.findByText('版本化 Canon 审阅未启用。');
  });
});
