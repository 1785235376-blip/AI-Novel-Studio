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
export type BailianConfigurationCheck = { valid: boolean; code: 'REGION_REQUIRED' | 'MODEL_REQUIRED' | 'MODEL_FORMAT_INVALID' | 'FORMAT_VALID'; message: string; base_url?: string };
function configurationCheck(catalog: BailianPresetCatalog, region: string, model: string): BailianConfigurationCheck {
 const selected = catalog.regions.find(item => item.id === region);
 if (!selected) return { valid: false, code: 'REGION_REQUIRED', message: '请先按实际 API 账户选择地区。' };
 if (!model) return { valid: false, code: 'MODEL_REQUIRED', message: '请填写账户中实际可用的文本模型 ID。' };
 if (typeof model !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(model)) return {
   valid: false, code: 'MODEL_FORMAT_INVALID', message: '模型 ID 格式无效：使用 1–200 个字母、数字或 . _ : / -，首位须为字母或数字；不接受空格、引号或命令字符。' };
 return { valid: true, code: 'FORMAT_VALID', message: '本地格式预检通过（未连接）', base_url: selected.base_url };
}
/** Existing preset constants only. No key read, network, registration or settings write. */
export function checkBailianConfiguration(catalog: BailianPresetCatalog, region: string, model: string): BailianConfigurationCheck {
 return configurationCheck(checkedBailianPresets(catalog), region, model);
}
export function bailianHostPreview(catalog:BailianPresetCatalog,region:string,model:string):string|undefined{
 const checked=checkedBailianPresets(catalog);if(!configurationCheck(checked,region,model).valid)return;
 return `${checked.region_variable}=${region}\n${checked.model_variable}=${model}`;
}

export type BailianPresetProblem = { code: string; title: string; action: string };
/** Classifies the original HOST preset read, never a provider connection test.
 * Arbitrary response messages/details/codes may contain private values and are
 * deliberately not copied to the view. Retry remains an explicit user action. */
export function bailianPresetReadProblem(reason: unknown): BailianPresetProblem {
 if (reason instanceof ApiError) {
  const { status, code } = reason.problem;
  if (code === 'STUDIO_RESPONSE_INVALID' || code === 'MODEL_CENTER_SECRET_VALUE_REJECTED') return {
   code: 'PRESET_RESPONSE_INVALID', title: '宿主预设响应无法核验', action: '没有显示响应内容。请确认宿主版本与当前客户端兼容，再手动读取；不要把密钥或原始响应粘贴到模型 ID 中。' };
  if (code === 'MODEL_CENTER_CATALOG_SCOPE_MISMATCH' || status === 409) return {
   code: 'PRESET_CONTEXT_CHANGED', title: '项目或分支上下文已变化', action: '请重新打开目标项目或分支后手动读取；旧结果不能用于当前上下文。' };
  if (status === 401) return { code: 'PRESET_SESSION_REQUIRED', title: '宿主会话需要重新登录', action: '请重新登录本地宿主会话后手动读取。这不是百炼 API Key 的认证结论。' };
  if (status === 403) return { code: 'PRESET_READ_DENIED', title: '当前会话没有预设读取权限', action: '请核对当前项目、分支和会话权限；不会自动切换凭据或重试。' };
  if (status === 404) return { code: 'PRESET_UNAVAILABLE', title: '当前宿主尚未提供百炼预设', action: '请核对宿主版本与预设功能是否可用；不需要在此修改云端账号或购买额度。' };
  if (status === 429) return { code: 'PRESET_RATE_LIMITED', title: '宿主请求受到限流', action: '请稍后手动读取；不会自动重试，也不会发起模型请求。' };
  if (Number.isInteger(status) && status >= 500 && status <= 599) return {
   code: 'PRESET_HOST_UNAVAILABLE', title: '宿主预设服务暂不可用', action: '请检查本地宿主服务是否正常，再手动读取；此结果不能判断百炼云端是否可用。' };
 }
 return { code: 'PRESET_READ_INCOMPLETE', title: '宿主预设读取未完成', action: '请检查与本地宿主的连接后手动读取；未展示原始错误内容，也不会自动外发或重试。' };
}
