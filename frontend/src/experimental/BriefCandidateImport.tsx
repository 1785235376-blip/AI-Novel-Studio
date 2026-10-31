import {useLayoutEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import {briefFields,type BriefText} from './personalSkillBrief';
import {parseBriefModelCandidate} from './briefModelCandidate';
type Props={active:boolean;disabled:boolean;current:BriefText;onApply:(value:BriefText)=>void};
export function BriefCandidateImport(props:Props){
 const [,bump]=useState(0);
 const [input,setInput]=useState(''),[error,setError]=useState(''),[preview,setPreview]=useState<{input:string;base:BriefText;value:BriefText}>();
 const live=useRef(props);live.current=props;const alive=useRef(true),composing=useRef(false),textarea=useRef<HTMLTextAreaElement>(null),used=useRef<object>();
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useLayoutEffect(()=>{if(!props.active||props.disabled)setPreview(undefined);},[props.active,props.disabled]);
 const revision=useRef(0),owner=useRef({active:props.active,disabled:props.disabled,base:props.current});
 if(owner.current.active!==props.active||owner.current.disabled!==props.disabled||owner.current.base!==props.current){revision.current++;owner.current={active:props.active,disabled:props.disabled,base:props.current};}
 const invalidate=()=>{revision.current++;bump(revision.current);setPreview(undefined);};
 const captured=revision.current;
 const current=()=>revision.current===captured&&alive.current&&live.current.active&&!live.current.disabled&&live.current.current===props.current&&!composing.current;
 const visible=preview&&preview.base===props.current&&preview.input===input&&props.active&&!props.disabled?preview:undefined;
 return <details><summary>导入模型整理候选（人工核对）</summary><p>可在创作画布的“写作简报整理”起步方案中明确运行并审核，再将输出粘贴到这里。本入口不调用模型、不核实模型来源，也不保存或执行插件。</p>
  <label>待审核简报 JSON<textarea ref={textarea} value={input} maxLength={128000} disabled={props.disabled||!props.active} onChange={e=>{invalidate();setInput(e.target.value);setError('');}} onCompositionStart={()=>{invalidate();composing.current=true;}} onCompositionEnd={e=>{invalidate();composing.current=false;setInput(e.currentTarget.value);}}/></label>
  <Button disabled={props.disabled||!props.active||!input.trim()} onClick={()=>{if(!current()||textarea.current?.value!==input)return;try{setPreview({input,base:props.current,value:parseBriefModelCandidate(input)});setError('');}catch(e){setPreview(undefined);setError(e instanceof Error?e.message:'候选无效。');}}}>比较四项简报内容</Button>
  {error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  {visible&&<section aria-label="简报候选差异">{briefFields.map(([key,label])=><div key={key}><h4>{label}</h4><p>原内容</p><pre>{props.current[key]}</pre><p>候选内容</p><pre>{visible.value[key]}</pre></div>)}<p>仅替换四项正文；身份、许可和模板安装仍由你单独确认。此候选来源未经验证，不代表官方收录。</p><Button onClick={()=>{if(!current()||textarea.current?.value!==input||live.current.current!==visible.base||used.current===visible)return;used.current=visible;setPreview(undefined);props.onApply(structuredClone(visible.value));}}>确认替换四项正文</Button></section>}
 </details>;
}
