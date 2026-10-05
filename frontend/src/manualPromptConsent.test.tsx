// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {api} from './api';
import {useStudio} from './store';
import {VisionAnalysisPanel} from './novel/VisionAnalysisPanel';
import {SpeechSynthesisPanel} from './novel/SpeechSynthesisPanel';
import {AudioGenerationPanel} from './novel/AudioGenerationPanel';
import {ImageGenerationPanel} from './novel/ImageGenerationPanel';
import {AiControlCenter} from './ui/AiControlCenter';

const scope={workspaceId:'workspace',projectId:'n1',storylineId:'story',branchId:'branch-a'};
const consent=()=>screen.getByRole('checkbox',{name:/允许本次向/}) as HTMLInputElement;
const audioProviders=[{provider_id:'cloud-audio',display_name:'Cloud Audio',default_model:'speech-model',local:false,configured:true,capabilities:['TTS','SFX','AUDIO_EDIT']},{provider_id:'local-audio',display_name:'Local Audio',default_model:'local-model',local:true,configured:true,capabilities:['TTS','SFX']}];

beforeEach(()=>{
  useStudio.setState({sessionToken:'session-a',actor:{id:'actor-a',displayName:'Actor',workspaceId:'workspace'},scope,novelId:'n1',textModel:{providerId:'deepseek',modelId:'deepseek-chat'}});
  vi.spyOn(api,'visualMemories').mockResolvedValue({items:[]});
  vi.spyOn(api,'speechGenerations').mockResolvedValue({items:[]});
  vi.spyOn(api,'imageGenerations').mockResolvedValue({items:[]});
  vi.spyOn(api,'imageJobs').mockResolvedValue({items:[]});
  vi.spyOn(api,'audioProviders').mockResolvedValue({items:audioProviders} as any);
  vi.spyOn(api,'assetProviders').mockResolvedValue({items:[{provider_id:'ddshub',display_name:'DDSHub',default_model:'gpt-image-2',configured:true,registered:true,local:false},{provider_id:'comfyui',display_name:'ComfyUI',default_model:'local-image',configured:true,registered:true,local:true}]} as any);
  vi.spyOn(api,'credentialStatus').mockResolvedValue({configured:false} as any);
  vi.spyOn(api,'textModels').mockResolvedValue([{provider_id:'deepseek',model_id:'deepseek-chat',display_name:'DeepSeek',available:true},{provider_id:'ollama',model_id:'qwen3:8b',display_name:'Qwen',available:true}]);
  vi.spyOn(api,'multimodalHealth').mockResolvedValue({});
  vi.spyOn(api,'userPreferences').mockResolvedValue({enabled:true,share_enabled:false,harness_enabled:false,items:[]});
  vi.spyOn(api,'harnessStatus').mockResolvedValue({configured:false,reachable:false});
  vi.spyOn(api,'harnessProcess').mockResolvedValue({running:false,pid:null});
  vi.spyOn(api,'harnessAccessAudit').mockResolvedValue({items:[]});
  vi.spyOn(api,'releaseReadiness').mockRejectedValue(new Error('synthetic unavailable'));
});
afterEach(()=>{cleanup();vi.restoreAllMocks();useStudio.setState({sessionToken:'',actor:undefined,scope:undefined,novelId:'',textModel:null});});

it('vision sends default denial and resets explicit consent on either text or reference edits',async()=>{
  const call=vi.spyOn(api,'visionAnalyze').mockResolvedValue({text:'synthetic result'} as any);
  render(<VisionAnalysisPanel novelId="n1"/>);
  fireEvent.change(screen.getByLabelText('图片 URL'),{target:{value:'https://example.test/ref.png'}});
  expect(consent().checked).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'分析图片'}));
  await waitFor(()=>expect(call).toHaveBeenCalledWith(expect.objectContaining({allow_cloud_prompt:false})));
  await waitFor(()=>expect(screen.getByRole('button',{name:'分析图片'})).toBeTruthy());
  fireEvent.click(consent());expect(consent().checked).toBe(true);
  fireEvent.change(screen.getByLabelText('分析要求'),{target:{value:'new manual question'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.change(screen.getByLabelText('图片 URL'),{target:{value:'https://example.test/other.png'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'分析图片'}));
  await waitFor(()=>expect(call).toHaveBeenLastCalledWith(expect.objectContaining({allow_cloud_prompt:true,prompt:'new manual question',image_url:'https://example.test/other.png'})));
  expect(consent().checked).toBe(false);
});

it('image queue freezes consent with the exact draft and resets after model or reference changes',async()=>{
  const queued=vi.spyOn(api,'createImageJob').mockResolvedValue({id:'job'});
  const direct=vi.spyOn(api,'imageGenerate').mockResolvedValue({asset_uri:'data:image/png;base64,c3ludGhldGlj'} as any);
  render(<ImageGenerationPanel novelId="n1"/>);
  await waitFor(()=>expect((screen.getByLabelText('图片模型') as HTMLInputElement).value).toBe('gpt-image-2'));
  fireEvent.click(consent());fireEvent.change(screen.getByLabelText('图片模型'),{target:{value:'another-model'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.change(screen.getByLabelText('多参考图地址'),{target:{value:'https://example.test/ref.png'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'保存到生成队列'}));
  await waitFor(()=>expect(queued).toHaveBeenCalledWith('n1',expect.objectContaining({allow_cloud_prompt:true,images:['https://example.test/ref.png'],model_id:'another-model'})));
  fireEvent.change(screen.getByLabelText('多参考图地址'),{target:{value:''}});
  fireEvent.change(screen.getByLabelText('图片 Provider'),{target:{value:'comfyui'}});
  expect(consent().checked).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'生成图片'}));
  await waitFor(()=>expect(direct).toHaveBeenCalledWith(expect.objectContaining({provider_id:'comfyui',allow_cloud_prompt:false})));
});

it('audio auto selection never grants an unnamed cloud provider consent',async()=>{
  const call=vi.spyOn(api,'audioGenerate').mockResolvedValue({provider_id:'local-audio',model_id:'local-model',status:'SUCCEEDED',audio_uri:'data:audio/wav;base64,eA=='} as any);
  render(<AudioGenerationPanel novelId="n1"/>);
  expect(consent().disabled).toBe(true);expect(consent().checked).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'生成音频'}));
  await waitFor(()=>expect(call).toHaveBeenCalledWith(expect.objectContaining({provider_id:'auto',allow_cloud_prompt:false})));
  await screen.findByRole('option',{name:'Cloud Audio'});
  fireEvent.change(screen.getByLabelText('音频制作 Provider'),{target:{value:'cloud-audio'}});
  fireEvent.click(consent());fireEvent.change(screen.getByLabelText('制作描述'),{target:{value:'new audio request'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'生成音频'}));
  await waitFor(()=>expect(call).toHaveBeenLastCalledWith(expect.objectContaining({provider_id:'cloud-audio',allow_cloud_prompt:true,prompt:'new audio request'})));
});

it('speech consent is explicit and resets when model, voice or text changes',async()=>{
  const call=vi.spyOn(api,'speechSynthesize').mockResolvedValue({audio_uri:'data:audio/wav;base64,eA=='} as any);
  render(<SpeechSynthesisPanel novelId="n1"/>);
  await screen.findByRole('option',{name:'Cloud Audio'});
  fireEvent.change(screen.getByLabelText('语音 Provider'),{target:{value:'cloud-audio'}});fireEvent.click(consent());
  fireEvent.change(screen.getByLabelText('模型'),{target:{value:'other-speech'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.change(screen.getByLabelText('音色'),{target:{value:'echo'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.change(screen.getByLabelText('朗读文本'),{target:{value:'manual text'}});expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'生成语音'}));
  await waitFor(()=>expect(call).toHaveBeenCalledWith(expect.objectContaining({allow_cloud_prompt:true,text:'manual text',model_id:'other-speech'})));
});

it('control chat sends only manual question and consent, and preserves colon-containing model IDs',async()=>{
  const call=vi.spyOn(api,'agentChat').mockResolvedValue({message:'synthetic answer'} as any);
  const {container}=render(<AiControlCenter/>);
  await screen.findByRole('option',{name:'Qwen · ollama'});
  fireEvent.change(container.querySelector('.ai-control-center__routing select')!,{target:{value:'ollama:qwen3:8b'}});
  expect(useStudio.getState().textModel).toEqual({providerId:'ollama',modelId:'qwen3:8b'});
  fireEvent.change(screen.getByPlaceholderText('询问软件能力、创作流程或当前模型配置'),{target:{value:'manual question'}});
  expect(consent().checked).toBe(false);
  fireEvent.click(consent());fireEvent.click(screen.getByRole('button',{name:'发送'}));
  await waitFor(()=>expect(call).toHaveBeenCalledWith({message:'manual question',provider_id:'ollama',model_id:'qwen3:8b',allow_cloud_prompt:true}));
  expect(call.mock.calls[0][0]).not.toHaveProperty('context');
});

const panels=['vision','speech','audio','image','control'] as const;
for(const panel of panels)it(`${panel} drops late responses and consent across actor, session and branch changes`,async()=>{
  let resolve!:(value:any)=>void;
  const promise=new Promise<any>(done=>{resolve=done});
  let call;
  if(panel==='vision'){call=vi.spyOn(api,'visionAnalyze').mockReturnValue(promise);render(<VisionAnalysisPanel novelId="n1"/>);fireEvent.change(screen.getByLabelText('图片 URL'),{target:{value:'https://example.test/ref.png'}});}
  else if(panel==='speech'){call=vi.spyOn(api,'speechSynthesize').mockReturnValue(promise);render(<SpeechSynthesisPanel novelId="n1"/>);}
  else if(panel==='audio'){call=vi.spyOn(api,'audioGenerate').mockReturnValue(promise);render(<AudioGenerationPanel novelId="n1"/>);}
  else if(panel==='image'){call=vi.spyOn(api,'imageGenerate').mockReturnValue(promise);render(<ImageGenerationPanel novelId="n1"/>);await waitFor(()=>expect((screen.getByLabelText('图片模型') as HTMLInputElement).value).toBe('gpt-image-2'));}
  else{call=vi.spyOn(api,'agentChat').mockReturnValue(promise);render(<AiControlCenter/>);await screen.findByRole('option',{name:'DeepSeek · deepseek'});fireEvent.change(screen.getByPlaceholderText('询问软件能力、创作流程或当前模型配置'),{target:{value:'question'}});}
  fireEvent.click(screen.getByRole('button',{name:{vision:'分析图片',speech:'生成语音',audio:'生成音频',image:'生成图片',control:'发送'}[panel]}));
  await waitFor(()=>expect(call).toHaveBeenCalledTimes(1));
  act(()=>useStudio.setState({sessionToken:'session-b',actor:{id:'actor-b',workspaceId:'workspace',displayName:'Other'},scope:{...scope,branchId:'branch-b'}}));
  await act(async()=>resolve({message:'STALE SECRET',text:'STALE SECRET',audio_uri:'https://example.test/stale-secret.wav',asset_uri:'https://example.test/stale-secret.png',status:'SUCCEEDED',provider_id:'old',model_id:'old'}));
  expect(screen.queryByText('STALE SECRET')).toBeNull();
  expect(document.body.innerHTML).not.toContain('stale-secret');
  expect(consent().checked).toBe(false);
});

it('an image history preview remains available when its saved prompt replaces the draft',async()=>{
  vi.mocked(api.imageGenerations).mockResolvedValue({items:[{id:'h',prompt:'historical prompt',asset_uri:'https://example.test/history.png',provider_id:'ddshub',model_id:'history-model'}]});
  render(<ImageGenerationPanel novelId="n1"/>);
  await screen.findByText('生成历史（1）');
  fireEvent.click(screen.getByRole('button',{name:'预览'}));
  await waitFor(()=>expect(screen.getByAltText('生成结果').getAttribute('src')).toBe('https://example.test/history.png'));
  expect((screen.getByLabelText('生成描述') as HTMLTextAreaElement).value).toBe('historical prompt');
});

for(const field of ['session','actor','workspace','project','storyline','branch'] as const)it(`consent cannot survive an isolated ${field} identity change or an ABA return`,async()=>{
  render(<VisionAnalysisPanel novelId="n1"/>);
  fireEvent.click(consent());expect(consent().checked).toBe(true);
  const previous=useStudio.getState();
  act(()=>{
    if(field==='session')useStudio.setState({sessionToken:'session-changed'});
    else if(field==='actor')useStudio.setState({actor:{id:'actor-changed',workspaceId:'workspace',displayName:'Other'}});
    else useStudio.setState({scope:{...scope,[{workspace:'workspaceId',project:'projectId',storyline:'storylineId',branch:'branchId'}[field]]:'changed'}});
    useStudio.setState({sessionToken:previous.sessionToken,actor:previous.actor,scope:previous.scope});
  });
  expect(consent().checked).toBe(false);
});
