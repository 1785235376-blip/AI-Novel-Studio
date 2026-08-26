import {useEffect,useRef,useState} from 'react';
import {RefreshCw} from 'lucide-react';
import {Button} from '../ui/primitives';
import {api} from '../api';
import {clearDeepSeekSessionCredential,setDeepSeekSessionCredential} from '../packagedHost';
import './credential.css';

type Props={configured:boolean;onRefresh:()=>Promise<boolean>;vaultMode?:boolean;onSaveVault?: (value:string)=>Promise<boolean>;onDeleteVault?:()=>Promise<boolean>;onTestVault?:()=>Promise<boolean>};
type Pending='set'|'clear'|'refresh'|null;
const encoder=new TextEncoder();
const wait=(milliseconds:number)=>new Promise(resolve=>setTimeout(resolve,milliseconds));
const refreshTimeout=()=>new Promise<boolean>(resolve=>setTimeout(()=>resolve(false),5000));

export function DeepSeekCredentialControl({configured,onRefresh,vaultMode=false,onSaveVault=async value=>{try{await api.saveCredential('deepseek',value);return true}catch{return false}},onDeleteVault=async()=>{try{await api.deleteCredential('deepseek');return true}catch{return false}},onTestVault=async()=>{try{return (await api.testCredential('deepseek')).reachable}catch{return false}}}:Props){
  const [credential,setCredential]=useState('');
  const [editing,setEditing]=useState(!configured);
  const [pending,setPending]=useState<Pending>(null);
  const [error,setError]=useState('');
  const inputRef=useRef<HTMLInputElement>(null);
  useEffect(()=>{if(!configured)setEditing(true);else if(pending===null)setEditing(false)},[configured,pending]);
  async function refreshState(){return Promise.race([onRefresh(),refreshTimeout()])}
  async function awaitState(expected:boolean){for(let attempt=0;attempt<10;attempt+=1){if(await refreshState()===expected)return true;await wait(500)}return false}
  async function refresh(){setPending('refresh');setError('');try{await refreshState()}catch{setError('未能刷新配置状态，请稍后重试。')}finally{setPending(null)}}
  async function submit(){
    if(!credential||encoder.encode(credential).length>1024||/[\0\r\n]/.test(credential)){setError('请输入有效的 DeepSeek API Key。');return}
    const value=credential;setPending('set');setError('');const sent=vaultMode&&onSaveVault?await onSaveVault(value):setDeepSeekSessionCredential(value);setCredential('');if(inputRef.current)inputRef.current.value='';
    if(!sent){setPending(null);setError('未能完成配置，请重新输入密钥后再试。');return}
    const accepted=await awaitState(true);setPending(null);if(!accepted)setError('未能完成配置，请重新输入密钥后再试。');
  }
  async function clear(){
    setPending('clear');setError('');setCredential('');
    const cleared=vaultMode&&onDeleteVault?await onDeleteVault():clearDeepSeekSessionCredential();
    if(!cleared){setPending(null);setError('未能清除配置，请稍后重试。');return}
    const accepted=await awaitState(false);setPending(null);if(!accepted)setError('未能清除本次会话配置，请稍后重试。');
  }
  if(configured&&!editing)return <section className="novel-credential-control" aria-label="DeepSeek 凭据配置"><div><strong>{vaultMode?'已安全保存 DeepSeek API Key':'本次会话已配置'}</strong><span>{vaultMode?'密钥保存在 Windows Credential Manager 中。':'关闭应用后不会保留。'}</span></div><div className="novel-credential-actions"><Button type="button" disabled={pending!==null} onClick={async()=>{setPending('refresh');setError('');try{const ok=vaultMode&&onTestVault?await onTestVault():await refreshState();if(!ok)setError(vaultMode?'凭据检测未通过。':'未能刷新配置状态，请稍后重试。')}catch{setError(vaultMode?'凭据检测失败，请稍后重试。':'未能刷新配置状态，请稍后重试。')}finally{setPending(null)}}}><RefreshCw aria-hidden="true"/>{pending==='refresh'?(vaultMode?'正在检测…':'正在刷新…'):(vaultMode?'检测连接':'刷新状态')}</Button><Button type="button" disabled={pending!==null} onClick={()=>{setCredential('');setError('');setEditing(true)}}>更换密钥</Button><Button type="button" variant="ghost" disabled={pending!==null} onClick={clear}>{pending==='clear'?'正在清除…':(vaultMode?'删除':'清除')}</Button></div>{error&&<p className="novel-error" role="alert">{error}</p>}</section>;
  return <section className="novel-credential-control" aria-label="DeepSeek 会话配置"><div><strong>{configured?'更换 DeepSeek API Key':'DeepSeek API Key'}</strong><span id="deepseek-session-help">仅在本次运行期间使用，关闭应用后不会保留。</span></div><label htmlFor="deepseek-session-credential">DeepSeek API Key</label><input ref={inputRef} id="deepseek-session-credential" type="password" value={credential} aria-describedby="deepseek-session-help" autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} disabled={pending!==null} onChange={event=>setCredential(event.target.value)}/><div className="novel-credential-actions"><Button type="button" disabled={pending!==null} onClick={refresh}><RefreshCw aria-hidden="true"/>{pending==='refresh'?'正在刷新…':'刷新状态'}</Button><Button variant="primary" type="button" disabled={pending!==null||!credential} onClick={submit}>{pending==='set'?'正在配置…':'配置此会话'}</Button>{configured&&<Button type="button" disabled={pending!==null} onClick={()=>{setCredential('');setError('');setEditing(false)}}>取消</Button>}</div>{error&&<p className="novel-error" role="alert">{error}</p>}</section>;
}
