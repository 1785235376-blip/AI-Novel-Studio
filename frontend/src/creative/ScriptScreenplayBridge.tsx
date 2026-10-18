import {useEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import type {CreativeDocument} from './types';
type Props={source:CreativeDocument;available:boolean;isCurrent:()=>boolean;onCreate:()=>void};
export function scriptScenePreview(source:CreativeDocument){
 if(source.mode!=='SCRIPT'||!source.id||!Number.isSafeInteger(source.version)||source.version<1||source.status==='ARCHIVED'||typeof source.script?.body!=='string')throw new Error('请先读取有效的已保存通用脚本。');
 const points=Array.from(source.script.body);if(!source.script.body.trim()||points.length>64000)throw new Error('脚本文本须为 1–64000 字符。');
 return Array.from({length:Math.ceil(points.length/16000)},(_,index)=>{const part=points.slice(index*16000,(index+1)*16000);return {number:index+1,characters:part.length,snippet:part.slice(0,120).join('')};});
}
/** An explicit staging choice only. Original CreativeWorkspace owns the mutation. */
export function ScriptScreenplayBridge(props:Props){
 const latest=useRef(props);latest.current=props;const alive=useRef(true),consent=useRef<object>(),consumed=useRef<object>();
 const owner=useRef({source:props.source,available:props.available,token:{}});
 if(owner.current.source!==props.source||owner.current.available!==props.available)owner.current={source:props.source,available:props.available,token:{}};
 const token=owner.current.token;const [confirmed,setConfirmed]=useState<object>();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const current=()=>alive.current&&latest.current.available&&latest.current.isCurrent()&&owner.current.token===token;
 let parts:ReturnType<typeof scriptScenePreview>|undefined,error='';try{parts=scriptScenePreview(props.source);}catch(reason){error=reason instanceof Error?reason.message:'脚本预览不可用。';}
 return <section aria-label="通用脚本转剧本底稿"><h3>从已保存通用脚本建立剧本底稿</h3><p>保留原文顺序与全部文字，每 16000 字符分为一段场景动作。不会分析场景、分配人物对白或调用模型；请在新剧本中人工整理后，再交给导演台。保留来源版本绑定，原脚本变化时需重新核对；原脚本保持不变。</p>{error?<StatusMessage tone="warning">{error}</StatusMessage>:<><p>来源 {props.source.title} · v{props.source.version} · {parts!.length} 个文本段</p><details><summary>核对文本段预览</summary><ol>{parts!.map(part=><li key={part.number}>文本段 {part.number} · {part.characters} 字符<p>{part.snippet}{part.characters>120?'…':''}</p></li>)}</ol></details><label><input type="checkbox" disabled={!props.available} checked={confirmed===token} onChange={event=>{if(!current())return;consent.current=event.target.checked?token:undefined;setConfirmed(consent.current);}}/>确认从此已保存版本建立独立的新剧本底稿</label><Button disabled={!props.available||confirmed!==token} onClick={()=>{if(!current()||consent.current!==token||consumed.current===token)return;consumed.current=token;consent.current=undefined;setConfirmed(undefined);latest.current.onCreate();}}>确认建立剧本底稿</Button></>}</section>;
}
