import {useEffect,useState} from 'react';
import {api} from '../api';
import {PipelineStatusPanel} from './PipelineStatusPanel';

export function ScreenplayPipelinePanel({novelId,screenplayId}:{novelId?:string;screenplayId?:string}){const [ready,setReady]=useState(false);useEffect(()=>{setReady(Boolean(novelId&&screenplayId));},[novelId,screenplayId]);return ready?<PipelineStatusPanel novelId={novelId} screenplayId={screenplayId}/>:null}
