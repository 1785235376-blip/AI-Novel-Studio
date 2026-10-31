import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { fillPromptVariables, promptVariableNames } from './promptVariables';
import { useTz } from '../i18n'; // [HERMIA-FE-20261031 VERA-EN]
type Props={text:string;owner:object;scope:string;disabled:boolean;onApply:(text:string)=>void};
export function PromptVariablesPanel(props:Props){
 const z=useTz();
 const parsed=useMemo(()=>{try{return {names:promptVariableNames(props.text),error:''};}catch(error){return {names:[],error:error instanceof Error?error.message:'无法读取变量。'};}},[props.text]);
 const [values,setValues]=useState<Record<string,string>>({}),[error,setError]=useState(''),[confirmed,setConfirmed]=useState(false),[composing,setComposing]=useState(false);
 type Preview={result:ReturnType<typeof fillPromptVariables>;token:object;edit:number};
 const [preview,setPreview]=useState<Preview>();const live=useRef(props);live.current=props;
 const alive=useRef(true),ime=useRef(false),edit=useRef(0),consent=useRef<Preview>(),proof=useRef(preview);proof.current=preview;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;consent.current=undefined;};},[]);
 const source=[props.text,props.owner,props.scope,props.disabled];const owner=useRef({source,token:{}});if(source.some((value,index)=>value!==owner.current.source[index]))owner.current={source,token:{}};const token=owner.current.token;
 const current=()=>alive.current&&!live.current.disabled&&!ime.current&&owner.current.token===token;
 function reset(){edit.current++;consent.current=undefined;proof.current=undefined;setPreview(undefined);setConfirmed(false);setError('');}
 useLayoutEffect(()=>{reset();setValues({});ime.current=false;setComposing(false);},[props.scope,props.owner]);
 const visible=preview&&preview.token===token&&preview.edit===edit.current?preview:undefined;
 if(!parsed.names.length&&!parsed.error)return null;
 return <details aria-label={z('Prompt 变量填写')}><summary>{z(`填写提示词变量 · ${parsed.names.length} 个`)}</summary><p>{z('只识别正文中的')} {'{{'}{z('变量名')}{'}}'}{z('，变量名可用文字、数字和下划线。前面紧接反斜杠的标记保持原样。值按字面填入一次，不执行代码、读取文件或调用模型。')}</p>
  {parsed.error&&<StatusMessage tone="warning">{z(parsed.error)}</StatusMessage>}
  <fieldset disabled={props.disabled} onCompositionStart={()=>{ime.current=true;setComposing(true);reset();}} onCompositionEnd={()=>{ime.current=false;setComposing(false);reset();}}><legend>{z('本次变量值（不会单独保存）')}</legend>
   {parsed.names.map(name=><label key={name}>{z('变量')} {name}<textarea rows={2} maxLength={8192} value={Object.hasOwn(values,name)?values[name]:''} onChange={event=>{if(alive.current&&!live.current.disabled&&owner.current.token===token){reset();setValues({...values,[name]:event.target.value});}}}/></label>)}
  </fieldset>
  <Button disabled={props.disabled||composing||!!parsed.error||!parsed.names.length} onClick={()=>{if(!current())return;reset();try{const next={result:fillPromptVariables(props.text,values),token,edit:edit.current};proof.current=next;setPreview(next);}catch(reason){setError(reason instanceof Error?reason.message:'填写预览失败。');}}}>{z('预览变量填写结果')}</Button>
  {error&&<StatusMessage tone="warning">{z(error)}</StatusMessage>}
  {visible&&<section aria-label={z('变量填写正文预览')}><p>{z(`${visible.result.replacements} 处替换 · ${visible.result.bytes} 字节。原正文尚未修改。`)}</p><pre>{visible.result.text}</pre>
   <label><input type="checkbox" checked={confirmed} disabled={props.disabled||composing} onChange={event=>{if(current()){consent.current=event.target.checked?visible:undefined;setConfirmed(event.target.checked);}}}/>{z('已核对完整正文，替换当前本地草稿')}</label>
   <Button disabled={props.disabled||composing||!confirmed} onClick={()=>{if(!current()||proof.current!==visible||consent.current!==visible||visible.edit!==edit.current)return;reset();props.onApply(visible.result.text);}}>{z('将变量结果填入正文草稿')}</Button>
   <p>{z('只修改正文，其他参数和引用绑定保持不变。使用原保存按钮才会创建修订。')}</p>
  </section>}
 </details>;
}
