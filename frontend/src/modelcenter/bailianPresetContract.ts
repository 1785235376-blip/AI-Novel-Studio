import {ApiError} from '../api';
export type BailianPresetCatalog={contract:'studio-bailian-text-preset-catalog/1';provider_id:'aliyun-bailian';regions:{id:string;label:string;base_url:string}[];region_variable:'ALIYUN_BAILIAN_REGION';model_variable:'ALIYUN_BAILIAN_MODEL';endpoint_family:'DASHSCOPE_SHARED_PAY_AS_YOU_GO';modality:'TEXT';enable_thinking:false;model_id_required:true;current_configuration_included:false;credential_value_included:false;configuration_applied:false;network_called:false;model_called:false;official_reference:'https://www.alibabacloud.com/help/en/model-studio/base-url'};
const endpoints:Record<string,string>={'cn-beijing':'https://dashscope.aliyuncs.com/compatible-mode/v1','ap-southeast-1':'https://dashscope-intl.aliyuncs.com/compatible-mode/v1','us-east-1':'https://dashscope-us.aliyuncs.com/compatible-mode/v1','cn-hongkong':'https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1'};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'百炼预设回执无效，未显示配置。'});}
function exact(value:unknown,keys:string[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))invalid();const r=value as Record<string,unknown>;if(Object.keys(r).length!==keys.length||keys.some(k=>!Object.hasOwn(r,k)))invalid();return r;}
export function checkedBailianPresets(value:unknown):BailianPresetCatalog{
 const flags=['enable_thinking','current_configuration_included','credential_value_included','configuration_applied','network_called','model_called'];
 const r=exact(value,['contract','provider_id','regions','region_variable','model_variable','endpoint_family','modality','model_id_required','official_reference',...flags]);
 if(r.contract!=='studio-bailian-text-preset-catalog/1'||r.provider_id!=='aliyun-bailian'||r.region_variable!=='ALIYUN_BAILIAN_REGION'||r.model_variable!=='ALIYUN_BAILIAN_MODEL'||r.endpoint_family!=='DASHSCOPE_SHARED_PAY_AS_YOU_GO'||r.modality!=='TEXT'||r.model_id_required!==true||r.official_reference!=='https://www.alibabacloud.com/help/en/model-studio/base-url'||flags.some(k=>r[k]!==false)||!Array.isArray(r.regions)||r.regions.length!==4)invalid();
 const seen=new Set<string>();for(const value of r.regions){const region=exact(value,['id','label','base_url']);if(typeof region.id!=='string'||!Object.hasOwn(endpoints,region.id)||seen.has(region.id)||region.base_url!==endpoints[region.id]||typeof region.label!=='string'||!region.label||region.label.length>80||/[\u0000-\u001f]/.test(region.label))invalid();seen.add(region.id);}
 return structuredClone(value) as BailianPresetCatalog;
}
export function bailianHostPreview(catalog:BailianPresetCatalog,region:string,model:string):string|undefined{
 const checked=checkedBailianPresets(catalog);if(!checked.regions.some(r=>r.id===region)||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(model))return;
 return `${checked.region_variable}=${region}\n${checked.model_variable}=${model}`;
}
