import {useEffect,useState} from 'react';
import {api} from '../api';

export function AuthenticatedMedia({novelId,assetId,uri,kind,label}:{novelId?:string;assetId?:string;uri?:string;kind:'audio'|'video';label:string}){
 const [source,setSource]=useState(''),[error,setError]=useState('');
 useEffect(()=>{
  let active=true,objectUrl='';setSource('');setError('');
  const parsed=uri?.match(/^\/api\/assets\/([^/]+)\/download(?:\?|$)/),id=assetId||parsed?.[1];
  if(id&&novelId){void api.assetDownload(id,novelId).then(blob=>{if(!active)return;objectUrl=URL.createObjectURL(blob);setSource(objectUrl)}).catch(()=>{if(active)setError('音视频读取失败，请检查资产和当前权限。')})}
  else if(uri&&(/^(https?:\/\/|blob:)/i.test(uri)||uri.startsWith(`data:${kind}/`)))setSource(uri);
  else if(uri)setError('音视频地址不受支持。');
  return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl)};
 },[novelId,assetId,uri,kind]);
 if(error)return <p role="alert">{error}</p>;
 if(!source)return <p className="novel-help" role="status">正在读取音视频…</p>;
 return kind==='audio'?<audio src={source} controls preload="metadata" aria-label={label}/>:<video src={source} controls preload="metadata" aria-label={label}/>;
}
