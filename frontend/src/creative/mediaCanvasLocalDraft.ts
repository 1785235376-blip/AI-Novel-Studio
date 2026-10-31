import { studioGraphDraftKey,type StudioGraphDraftOwner } from './studioGraphLocalDraft';
import { checkedCanvasDefinition,type CanvasDefinition,type CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioClient } from './studioClient';
export type MediaCanvasLocalDraft={contract:'studio-media-view-draft/1';owner:StudioGraphDraftOwner;saved_at:string;request_id:string;
 base:Pick<CanvasViewRecord,'id'|'version'|'definition_digest'>|null;definition:CanvasDefinition;uncertain:boolean};
export const MEDIA_DRAFT_BYTES=600000;
export const mediaCanvasDraftKey=(owner:StudioGraphDraftOwner)=>studioGraphDraftKey(owner).replace('studio-graph-draft:','studio-media-view-draft:');
const hash=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('MEDIA_DRAFT_INVALID');return value as Record<string,unknown>;}
function exact(value:Record<string,unknown>,keys:string[]){if(Object.keys(value).length!==keys.length||keys.some(key=>!Object.hasOwn(value,key)))throw new Error('MEDIA_DRAFT_FIELDS_INVALID');}
export function readMediaCanvasLocalDraft(raw:string,owner:StudioGraphDraftOwner):MediaCanvasLocalDraft{
 if(typeof raw!=='string'||raw.length>MEDIA_DRAFT_BYTES||new TextEncoder().encode(raw).length>MEDIA_DRAFT_BYTES)throw new Error('MEDIA_DRAFT_TOO_LARGE');
 const value=object(JSON.parse(raw));exact(value,['contract','owner','saved_at','request_id','base','definition','uncertain']);
 const stored=object(value.owner),keys=Object.keys(owner);exact(stored,keys);if(keys.some(key=>stored[key]!==owner[key as keyof StudioGraphDraftOwner]))throw new Error('MEDIA_DRAFT_OWNER_CHANGED');
 if(value.contract!=='studio-media-view-draft/1'||typeof value.uncertain!=='boolean'||typeof value.saved_at!=='string'||value.saved_at.length>100||!Number.isFinite(Date.parse(value.saved_at))
   ||typeof value.request_id!=='string'||!/^view-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value.request_id))throw new Error('MEDIA_DRAFT_INVALID');
 let base:MediaCanvasLocalDraft['base']=null;
 if(value.base!==null){const row=object(value.base);exact(row,['id','version','definition_digest']);if(typeof row.id!=='string'||!row.id||row.id.length>240||/[\u0000-\u001f\u007f]/.test(row.id)||!Number.isSafeInteger(row.version)||Number(row.version)<1||!hash(row.definition_digest))throw new Error('MEDIA_DRAFT_BASE_INVALID');base={id:row.id,version:row.version as number,definition_digest:row.definition_digest as string};}
 return{contract:'studio-media-view-draft/1',owner:{...owner},saved_at:value.saved_at,request_id:value.request_id,base,definition:checkedCanvasDefinition(value.definition,true),uncertain:value.uncertain};
}
export function serializeMediaCanvasLocalDraft(value:MediaCanvasLocalDraft){const raw=JSON.stringify(value);readMediaCanvasLocalDraft(raw,value.owner);return raw;}
/** Current original owners only. The cache is never an access or execution grant. */
export async function verifyMediaCanvasRecovery(client:Pick<StudioClient,'overview'|'assets'|'graphs'>,snapshot:MediaCanvasLocalDraft,isCurrent:()=>boolean){
 const guard=()=>{if(!isCurrent())throw new Error('媒体草稿恢复身份已改变。');};
 const overview=async()=>{guard();const value=await client.overview();guard();if(value.project.id!==snapshot.owner.projectId||value.project.incarnation!==snapshot.owner.incarnation||!value.capabilities.can_mutate)throw new Error('项目代次或编辑权限已变化，未恢复旧草稿。');};
 await overview();let base:CanvasViewRecord|undefined;
 if(snapshot.base){if(!client.graphs.canvasViews)throw new Error('原媒体画布读取入口不可用。');base=await client.graphs.canvasViews.get(snapshot.base.id);guard();if(base.id!==snapshot.base.id||base.version!==snapshot.base.version||base.definition_digest!==snapshot.base.definition_digest)throw new Error('媒体画布服务端版本已变化，请先核对原版本。');}
 if(snapshot.definition.cards.length){const rows=(await client.assets()).items;guard();const byId=new Map(rows.map(row=>[row.id,row]));if(byId.size!==rows.length)throw new Error('素材目录标识不唯一。');
  for(const card of snapshot.definition.cards){const ref=card.asset,asset=ref&&byId.get(ref.asset_id);if(!ref||!asset||asset.deleted_at||asset.version!==ref.version||asset.sha256!==ref.digest||asset.kind!==ref.kind)throw new Error('草稿素材已变化或不可访问，未恢复旧引用。');}}
 await overview();return base;
}
