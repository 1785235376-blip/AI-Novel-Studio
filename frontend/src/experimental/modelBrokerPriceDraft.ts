import type {Row} from './api';
import type {BrokerRoute} from './modelBrokerClient';

export type ModelBrokerPriceDraft={expectedVersion:number;estimate:string;source:string;expiry:string;sourceExpiry:string;inputRate:string;outputRate:string};
const amount=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0&&value<=1_000_000_000_000;
/** Local editing projection of an existing owner receipt; never ranks or configures a route. */
export function modelBrokerPriceDraft(row:Row|undefined,route:BrokerRoute|undefined):ModelBrokerPriceDraft|undefined{
 if(!row||!route||row.route_id!==route.route_id||row.route_fingerprint!==route.fingerprint||row.currency!=='USD'||row.applicability!=='per_request'||!Number.isSafeInteger(row.version)||row.version<1||!amount(row.reserve_microusd)||typeof row.source!=='string'||!row.source.trim()||row.source.length>240)return;
 if([row.input_per_million_microusd,row.output_per_million_microusd].some(value=>value!=null&&!amount(value)))return;
 if(typeof row.expires_at!=='string'||!/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(row.expires_at))return;
 const date=new Date(row.expires_at);
 if(!Number.isFinite(date.getTime()))return;
 const expiry=new Date(date.getTime()-date.getTimezoneOffset()*60_000).toISOString().slice(0,-1);
 return {expectedVersion:row.version,estimate:String(row.reserve_microusd),source:row.source,expiry,sourceExpiry:row.expires_at,inputRate:row.input_per_million_microusd==null?'':String(row.input_per_million_microusd),outputRate:row.output_per_million_microusd==null?'':String(row.output_per_million_microusd)};
}
