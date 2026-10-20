import {create} from 'zustand';

export type LocalHostReceipt={session_mode:'LOCAL_HOST';actor_id:string};
/** Explicitly verified development Host credential; never persisted or exposed in query keys. */
export const useLocalHostSession=create<{token:string;actorId:string;epoch:number}>(()=>({token:'',actorId:'',epoch:0}));
export function bindLocalHostSession(token:string,receipt:LocalHostReceipt){
 if(receipt.session_mode!=='LOCAL_HOST'||!receipt.actor_id||!token.trim())throw new Error('本机可信会话验证未通过。');
 useLocalHostSession.setState(state=>({token:token.trim(),actorId:receipt.actor_id,epoch:state.epoch+1}));
}
export function clearLocalHostSession(){
 const state=useLocalHostSession.getState();
 if(state.token)useLocalHostSession.setState({token:'',actorId:'',epoch:state.epoch+1});
}
