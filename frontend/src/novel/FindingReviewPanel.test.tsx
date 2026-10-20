// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {FindingReviewPanel} from './FindingReviewPanel';
import {ApiError} from '../api';
import {useStudio} from '../store';
const mocks=vi.hoisted(()=>({flags:vi.fn(),list:vi.fn(),check:vi.fn(),review:vi.fn(),evidence:vi.fn()}));
vi.mock('../experimental/api',()=>({experimentalFeatures:mocks.flags}));
vi.mock('./findingReviewClient',()=>({findingReviewClient:()=>mocks}));
const chapter={id:'n:1',novel_id:'n',version:1,number:1,title:'Chapter',content:'Chapter words'} as any;
const row={id:'f',description:'Clock contradiction',finding_type:'TIMELINE',status:'OPEN',effective_status:'OPEN',review_version:1,source_digest:'a'.repeat(64),finding_fingerprint:'b'.repeat(64),stale_source:false,suppression_active:false,source:{chapter_id:'n:1',version:1,digest:'c'.repeat(64)},provenance:'AUTHOR_SUPPLIED_FACTS',review_history:[],feedback_reason:'',allowed_actions:['resolve','intentional','reopen','feedback']};
function show(){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><FindingReviewPanel projectId="n" chapter={chapter}/></QueryClientProvider>)}
beforeEach(()=>{mocks.flags.mockResolvedValue({features:{'experimental.finding_review_v1':true}});mocks.list.mockResolvedValue({items:[row]});mocks.check.mockResolvedValue({items:[row]});mocks.review.mockResolvedValue({...row,review_version:2});useStudio.setState({sessionToken:'',scope:undefined,actor:undefined});});
afterEach(()=>{cleanup();vi.clearAllMocks();});
describe('source-bound finding review',()=>{
  it('requires reason and human confirmation, cancellation writes nothing, and submits exact CAS tokens',async()=>{
    show();fireEvent.click(await screen.findByRole('button',{name:'审阅此问题'}));
    expect((screen.getByRole('button',{name:'确认保存审阅'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('审阅理由'),{target:{value:'This is deliberate'}});
    fireEvent.click(screen.getByRole('button',{name:'取消审阅'}));expect(mocks.review).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'审阅此问题'}));
    fireEvent.change(screen.getByLabelText('审阅理由'),{target:{value:'This is deliberate'}});
    fireEvent.click(screen.getByLabelText('已核对来源版本和证据'));
    fireEvent.click(screen.getByRole('button',{name:'确认保存审阅'}));fireEvent.click(screen.getByRole('button',{name:'确认保存审阅'}));
    await waitFor(()=>expect(mocks.review).toHaveBeenCalledTimes(1));
    expect(mocks.review).toHaveBeenCalledWith('continuity','f',expect.objectContaining({expected_version:1,source_digest:row.source_digest,finding_fingerprint:row.finding_fingerprint,reason:'This is deliberate',confirmed:true,action:'intentional'}));
  });
  it('opens exact historical evidence, closes it and shows a stable source-stale state',async()=>{
    mocks.list.mockResolvedValue({items:[{...row,stale_source:true,effective_status:'REVIEW_REQUIRED',allowed_actions:['reopen','feedback']}]});
    mocks.evidence.mockResolvedValue({navigation:{chapter_id:'n:1',chapter_version:1},chapter:{id:'n:1',version:1,content:'Historical exact words'},stale_source:true,evidence_ids:['ev']});
    show();expect(await screen.findByText(/原有意设置不再生效/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'打开确切来源 v1'}));
    expect(await screen.findByDisplayValue('Historical exact words')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'关闭来源'}));expect(screen.queryByDisplayValue('Historical exact words')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'审阅此问题'}));
    expect((screen.getByRole('option',{name:'这是有意设置'}) as HTMLOptionElement).disabled).toBe(true);
  });
  it('preserves review reason on conflict and does not retry automatically',async()=>{
    mocks.review.mockRejectedValue(new ApiError({status:409,code:'FINDING_VERSION_CONFLICT',message:'版本或证据已改变。审阅理由已保留，请刷新核对。'}));
    show();fireEvent.click(await screen.findByRole('button',{name:'审阅此问题'}));fireEvent.change(screen.getByLabelText('审阅理由'),{target:{value:'Keep this draft'}});fireEvent.click(screen.getByLabelText('已核对来源版本和证据'));fireEvent.click(screen.getByRole('button',{name:'确认保存审阅'}));
    expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.getByDisplayValue('Keep this draft')).toBeTruthy();expect(mocks.review).toHaveBeenCalledTimes(1);
  });
  it('reports disabled and unauthorized states without rendering returned stale rows',async()=>{
    mocks.flags.mockResolvedValueOnce({features:{'experimental.finding_review_v1':false}});const view=show();expect(await screen.findByText('此工作区未启用版本化问题审阅。')).toBeTruthy();expect(mocks.list).not.toHaveBeenCalled();view.unmount();
    mocks.list.mockRejectedValue(new ApiError({status:403,code:'FORBIDDEN',message:'当前身份无权读取或审阅此范围。'}));show();expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByText('Clock contradiction')).toBeNull();
  });
  it('discards late evidence after scope navigation',async()=>{
    let resolve!:(value:unknown)=>void;mocks.evidence.mockReturnValue(new Promise(r=>{resolve=r}));
    show();fireEvent.click(await screen.findByRole('button',{name:'打开确切来源 v1'}));
    useStudio.setState({sessionToken:'different-session'});
    resolve({navigation:{chapter_id:'n:1',chapter_version:1},chapter:{id:'n:1',version:1,content:'Old secret'},stale_source:false,evidence_ids:[]});
    await waitFor(()=>expect(screen.queryByDisplayValue('Old secret')).toBeNull());
  });
});
