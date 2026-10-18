import { ApiError } from '../api';
import type { RecordedMediaCommand } from './studioProductionClient';

export type ComicImageSource = { id: string; kind: 'COMIC_PANEL'; version: number; digest: string; reference_only: true;
  comic_panel: { panel_id: string; panel_digest: string; brief_digest: string; actor: string; scope_key: string; incarnation: string } };
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const hex = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const identifier = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value);
const text = (value: unknown, max: number): value is string => typeof value === 'string' && value.trim().length > 0 && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '漫画画格来源不完整，请重新读取核对。' }); }
export function checkedComicImageSource(value: unknown): ComicImageSource {
  if (!record(value) || Object.keys(value).some(key => !['id', 'kind', 'version', 'digest', 'reference_only', 'asset_kind', 'comic_panel'].includes(key))
    || !identifier(value.id) || value.kind !== 'COMIC_PANEL' || !Number.isSafeInteger(value.version) || Number(value.version) < 1
    || !hex(value.digest) || value.reference_only !== true || value.asset_kind != null || !record(value.comic_panel)) invalid();
  const pin = value.comic_panel;
  if (Object.keys(pin).length !== 6 || Object.keys(pin).some(key => !['panel_id', 'panel_digest', 'brief_digest', 'actor', 'scope_key', 'incarnation'].includes(key))
    || !(typeof pin.panel_id === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(pin.panel_id)) || !hex(pin.panel_digest) || !hex(pin.brief_digest) || !text(pin.actor, 240) || !hex(pin.scope_key) || !(typeof pin.incarnation === 'string' && /^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(pin.incarnation))) invalid();
  return { id: value.id, kind: 'COMIC_PANEL', version: Number(value.version), digest: value.digest, reference_only: true,
    comic_panel: { panel_id: pin.panel_id, panel_digest: pin.panel_digest, brief_digest: pin.brief_digest, actor: pin.actor, scope_key: pin.scope_key, incarnation: pin.incarnation } };
}
const parameterKeys = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'];
const nullableDefaults = [...parameterKeys, 'scale', 'denoising_strength', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels', 'output_format', 'fade_in_ms', 'fade_out_ms', 'target_peak_dbfs'];
export function checkedComicImageCommand(value: unknown): RecordedMediaCommand {
  if (!record(value) || Object.keys(value).some(key => !['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note'].includes(key))
    || value.operation_id !== 'm5.image.t2i' || value.allow_cloud !== false || !text(value.request_id, 100) || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(value.request_id)
    || !text(value.provider_id, 240) || !text(value.model_id, 240) || typeof value.prompt !== 'string' || !value.prompt.trim() || value.prompt.length > 16000
    || typeof value.license_note !== 'string' || value.license_note.length > 2000 || !record(value.parameters)
    || !Array.isArray(value.source_snapshots) || value.source_snapshots.length !== 1) invalid();
  const source = checkedComicImageSource(value.source_snapshots[0]), parameters: Record<string, string | number> = {};
  for (const [key, entry] of Object.entries(value.parameters)) {
    if (entry === null && nullableDefaults.includes(key)) continue;
    if (!parameterKeys.includes(key) || (typeof entry === 'number' ? !Number.isFinite(entry) : typeof entry !== 'string' || entry.length > 8000)) invalid();
    if (['width', 'height', 'steps', 'seed'].includes(key)) {
      const lower = key === 'seed' ? 0 : key === 'steps' ? 1 : 64, upper = key === 'seed' ? 2147483647 : key === 'steps' ? 150 : 2048;
      if (typeof entry !== 'number' || !Number.isSafeInteger(entry) || entry < lower || entry > upper) invalid();
    } else if (typeof entry !== 'string' || key === 'size' && !['auto', '1024x1024', '1536x1024', '1024x1536'].includes(entry)
      || key === 'quality' && !['auto', 'low', 'medium', 'high', 'standard', 'hd'].includes(entry)) invalid();
    parameters[key] = entry as string | number;
  }
  if ((parameters.width === undefined) !== (parameters.height === undefined) || parameters.width === undefined && parameters.size === undefined) invalid();
  return { ...value, parameters, source_snapshots: [source] } as RecordedMediaCommand;
}
export function hasComicImageSource(value: unknown): boolean {
  return record(value) && Array.isArray(value.source_snapshots) && value.source_snapshots.some(source => record(source) && (source.kind === 'COMIC_PANEL' || Object.hasOwn(source, 'comic_panel')));
}
export function checkedComicImageFields(value: unknown): void { if (hasComicImageSource(value)) checkedComicImageCommand(value); }
export function sameComicImageCommand(expected: unknown, value: unknown): boolean {
  if (!hasComicImageSource(expected)) return !hasComicImageSource(value);
  try {
    const before = checkedComicImageCommand(expected), after = checkedComicImageCommand(value);
    return ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'allow_cloud', 'license_note'].every(key => before[key as keyof RecordedMediaCommand] === after[key as keyof RecordedMediaCommand])
      && JSON.stringify(before.source_snapshots) === JSON.stringify(after.source_snapshots)
      && Object.keys(before.parameters).length === Object.keys(after.parameters).length && Object.entries(before.parameters).every(([key, entry]) => after.parameters[key] === entry);
  } catch { return false; }
}
