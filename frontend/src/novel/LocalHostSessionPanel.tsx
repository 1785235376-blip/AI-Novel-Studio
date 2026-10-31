import {useEffect,useRef,useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {api,ApiError} from '../api';
import {bindLocalHostSession,clearLocalHostSession,useLocalHostSession} from '../localHostSession';
import {isPackagedDesktopHost} from '../packagedHost';
import {useStudio} from '../store';
import {Button,Panel,StatusMessage} from '../ui/primitives';

export function LocalHostSessionPanel(){
 const teamToken=useStudio(state=>state.sessionToken),scope=useStudio(state=>state.scope);
 const session=useLocalHostSession(),client=useQueryClient();
 const [input,setInput]=useState(''),[pending,setPending]=useState(false),[error,setError]=useState('');
 const alive=useRef(true),flight=useRef(false);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 if(teamToken||scope||isPackagedDesktopHost())return null;
 function refresh(){client.removeQueries({predicate:query=>String(query.queryKey[0]).startsWith('agent-job')});}
 async function connect(){
  if(flight.current||!input.trim())return;
  flight.current=true;setPending(true);setError('');
  const value=input.trim(),epoch=useLocalHostSession.getState().epoch;
  try{
   const receipt=await api.validateLocalHostSession(value);
   const current=useStudio.getState();
   if(!alive.current||current.sessionToken||current.scope||isPackagedDesktopHost()||useLocalHostSession.getState().epoch!==epoch)return;
   bindLocalHostSession(value,receipt);setInput('');refresh();
  }catch(failure){
   if(alive.current)setError(failure instanceof ApiError&&failure.status===401?'本机访问凭证无效或已过期，请核对后重试。':'本机可信会话验证未通过，请检查本机服务模式后重试。');
  }finally{flight.current=false;if(alive.current)setPending(false)}
 }
 return <Panel title="本机可信会话"><section className="novel-draft-review">
  <p className="novel-help">本机开发 Host 的 Agent 任务需要已授权的访问凭证。验证后继续使用本机作品；凭证只保留在当前页面内存中，刷新后需重新验证。</p>
  {session.token?<><StatusMessage tone="success">已验证本机身份：{session.actorId}</StatusMessage><Button onClick={()=>{clearLocalHostSession();setInput('');setError('');refresh()}}>解绑本机可信会话</Button></>:<>
   <label>本机访问凭证<input type="password" value={input} autoComplete="off" onChange={event=>setInput(event.target.value)} disabled={pending}/></label>
   <Button variant="primary" loading={pending} disabled={!input.trim()||pending} onClick={()=>void connect()}>验证并绑定本机会话</Button>
  </>}
  {error&&<StatusMessage tone="error">{error}</StatusMessage>}
 </section></Panel>;
}
