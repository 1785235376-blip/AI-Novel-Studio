// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {CreationWorkbenchPanel} from './CreationWorkbenchPanel';
import {api} from '../api';
import {useStudio} from '../store';
vi.mock('../api',()=>({setCollaborationContext:vi.fn(),api:{creationReferenceData:vi.fn(),creationRecords:vi.fn(),reviewThreads:vi.fn(),saveCreationRecord:vi.fn(),creationRecordAction:vi.fn(),createReviewThread:vi.fn(),reviewThreadAction:vi.fn()},apiErrorView:(e:any)=>({message:e.message})}));
const row={id:'style-1',kind:'STYLE',title:'冷峻',description:'',instructions:'短句',acts:[],conflict:'',climax:'',ending:'',rules:[],privacy_level:'LOCAL_ONLY',chapter_ids:[],character_ids:[],location_ids:[],related_record_ids:[],story_route_id:null,version:2,status:'APPROVED',source_versions:{},history:[],updated_at:'2026-10-05',actor_id:'author'};
beforeEach(()=>{vi.clearAllMocks();useStudio.setState({writingInputs:{}});vi.mocked(api.creationRecords).mockResolvedValue({items:[]});vi.mocked(api.reviewThreads).mockResolvedValue({items:[]});vi.mocked(api.creationReferenceData).mockResolvedValue({characters:[],locations:[],story_routes:[]})});
afterEach(cleanup);
describe('creation workbench',()=>{
 it('saves a real style draft and keeps errors and input',async()=>{
  vi.mocked(api.saveCreationRecord).mockRejectedValueOnce(new Error('版本冲突'));
  render(<CreationWorkbenchPanel novelId="n"/>);
  await screen.findByText('此类型还没有记录');
  fireEvent.change(screen.getByLabelText('名称'),{target:{value:'克制'}});
  fireEvent.change(screen.getByLabelText(/可复用风格指令/),{target:{value:'简短句子'}});
  fireEvent.click(screen.getByRole('button',{name:'保存草稿'}));
  await screen.findByText(/版本冲突/);
  expect((screen.getByLabelText('名称') as HTMLInputElement).value).toBe('克制');
  expect(api.saveCreationRecord).toHaveBeenCalledWith('n',expect.objectContaining({kind:'STYLE',privacy_level:'LOCAL_ONLY',instructions:'简短句子'}),undefined,undefined,undefined);
 });
 it('selects only an approved record for generation without accepting body',async()=>{
  vi.mocked(api.creationRecords).mockResolvedValue({items:[row]});
  render(<CreationWorkbenchPanel novelId="n"/>);
  fireEvent.click(await screen.findByRole('button',{name:'用于写作'}));
  expect(useStudio.getState().writingInputs).toEqual({styleProfileId:'style-1'});
  expect(api.creationRecordAction).not.toHaveBeenCalled();
 });
 it('anchors a comment to current chapter version and actor stays server-owned',async()=>{
  vi.mocked(api.createReviewThread).mockResolvedValue({} as any);
  render(<CreationWorkbenchPanel novelId="n" initialComments chapter={{id:'n:1',novel_id:'n',title:'第一章',number:1,content:'原文',document:{},version:7,word_count:2,status:'DRAFT'}}/>);
  await screen.findByText('还没有评论');
  fireEvent.change(screen.getByLabelText('评论内容'),{target:{value:'核对动机'}});
  fireEvent.click(screen.getByRole('button',{name:'保存评论'}));
  await waitFor(()=>expect(api.createReviewThread).toHaveBeenCalledWith('n',{chapter_id:'n:1',chapter_version:7,quote:'',text:'核对动机'},undefined));
 });
 it('old unmounted requests cannot populate the new project',async()=>{
  let resolve!:Function;
  vi.mocked(api.creationRecords).mockImplementationOnce(()=>new Promise(r=>{resolve=r}));
  const first=render(<CreationWorkbenchPanel novelId="old"/>);first.unmount();
  render(<CreationWorkbenchPanel novelId="new"/>);
  await screen.findByText('此类型还没有记录');resolve({items:[row]});
  await new Promise(r=>setTimeout(r,0));expect(screen.queryByText('冷峻')).toBeNull();
 });
});
