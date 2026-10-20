import {blankGraph} from './graphDraft';
import type {StudioGraphDefinition,StudioGraphNode} from './studioGraphTypes';
const node=(id:string,text='author'):StudioGraphNode=>({id,definition_id:'text_input',definition_version:1,enabled:true,parameters:{text},position:{x:0,y:0}});
/** Fixed independent-review shape: JS 95998 / owner canonical 96032 at 31223. */
export function templateCapacitySource():StudioGraphDefinition{return {...blankGraph(),nodes:[node('A'),{id:'B',definition_id:'draft_prepare',definition_version:1,enabled:true,parameters:{},position:{x:400,y:0}}],edges:[{id:'Edge',source_node_id:'A',source_port:'text',target_node_id:'B',target_port:'text'}],presentation:{groups:[{id:'Child',name:'child',parent_id:'Parent',node_ids:['B']},{id:'Parent',name:'parent',node_ids:['A']}],notes:[{id:'Note',text:'字'.repeat(256),position:{x:0,y:250}}]}};}
export function templateCapacityTarget(total:number):StudioGraphDefinition{return {...blankGraph(),nodes:Array.from({length:4},(_,i)=>node('T'+i,'字'.repeat(Math.floor(total/4)+(i<total%4?1:0))))};}
