import {StatusMessage} from '../ui/primitives';
import {parsePronunciationRules,pronunciationPreview} from './voicePronunciation';
export function PronunciationPreview({text,rules}:{text:string;rules:string}){
 let result:ReturnType<typeof pronunciationPreview>|undefined,error='';
 try{result=pronunciationPreview(text,parsePronunciationRules(rules));}catch(reason){error=reason instanceof Error?reason.message:'无法预览当前规则。';}
 return <details><summary>预览发音替换后的朗读文本</summary><p>只在当前页面预览字面替换，不保存、不合成声音。原词按最长匹配同时替换，替换结果不会再次套用规则；实际读音仍需试听。</p>{error?<StatusMessage tone="warning">{error}</StatusMessage>:result&&<><p>{result.characters} 字符{result.truncated?'；仅显示前 4000 字符，完整文本未在这里改写。':'。'}</p><textarea aria-label="发音替换后的朗读文本预览" readOnly value={result.text}/></>}</details>;
}
