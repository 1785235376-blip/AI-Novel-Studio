import type { MediaCommand, RecordedMediaCommand, RecordedProductionSource } from './studioProductionClient';
import { checkedStoryboardShotContext } from './studioVideoRuntimeContract';
import { storyboardClosed, storyboardInvalid, storyboardRecord, storyboardResource, storyboardText, type ShotPin, type StoryboardReceipt, type StoryboardShot } from './studioStoryboardContract';

export type StoryboardSpeechPin = ShotPin & { dialogue_index: number };
export type StoryboardAudioRequest = { contract: 'studio-storyboard-audio-request/1'; shot_pin: StoryboardSpeechPin; command: RecordedMediaCommand;
  automatic_dispatch: false; model_called: false; output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW'; product_acceptance: 'LOCAL_REQUIRED' };
const legacyParameters = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'duration_seconds', 'frame_rate', 'in_ms', 'out_ms'];
export function checkedSpeechChoices(voice: unknown, rate: unknown) {
  const voice_id = storyboardResource(voice);
  if (typeof rate !== 'number' || !Number.isFinite(rate) || rate < 0.5 || rate > 2) storyboardInvalid();
  return { voice_id, speech_rate: rate };
}
export function checkedStoryboardSpeechPin(value: unknown): StoryboardSpeechPin {
  const row = storyboardRecord(value); storyboardClosed(row, ['document_snapshot', 'shot_id', 'shot_version', 'shot_digest', 'dialogue_index']);
  const { dialogue_index, ...shot } = row;
  if (typeof dialogue_index !== 'number' || !Number.isSafeInteger(dialogue_index) || dialogue_index < 0 || dialogue_index > 199) storyboardInvalid();
  return { ...checkedStoryboardShotContext(shot), dialogue_index };
}
const samePin = (left: StoryboardSpeechPin, right: StoryboardSpeechPin) => JSON.stringify(checkedStoryboardSpeechPin(left)) === JSON.stringify(checkedStoryboardSpeechPin(right));
export function checkedStoryboardSpeechCommand(value: unknown): RecordedMediaCommand {
  const row = storyboardRecord(value);
  storyboardClosed(row, ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note', 'storyboard_speech']);
  if (row.operation_id !== 'm8.audio.speech' || row.allow_cloud !== false) storyboardInvalid();
  const requestId = storyboardText(row.request_id, 100); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) storyboardInvalid();
  storyboardResource(row.provider_id); storyboardResource(row.model_id); storyboardText(row.prompt, 16000); storyboardText(row.license_note, 2000, true);
  const pin = checkedStoryboardSpeechPin(row.storyboard_speech), raw = storyboardRecord(row.parameters), parameters = checkedSpeechChoices(raw.voice_id, raw.speech_rate);
  if (Object.entries(raw).some(([key, value]) => !['voice_id', 'speech_rate'].includes(key) && (!legacyParameters.includes(key) || value !== null))) storyboardInvalid();
  if (!Array.isArray(row.source_snapshots) || row.source_snapshots.length !== 1) storyboardInvalid();
  const source = storyboardRecord(row.source_snapshots[0]);
  if (Object.keys(source).some(key => !['id', 'version', 'digest', 'kind', 'reference_only', 'asset_kind'].includes(key)) || source.kind !== 'CREATIVE_DOCUMENT'
    || source.asset_kind != null || source.reference_only !== true || ['id', 'version', 'digest'].some(key => source[key] !== pin.document_snapshot[key as keyof typeof pin.document_snapshot])) storyboardInvalid();
  const sources: RecordedProductionSource[] = [{ ...pin.document_snapshot, kind: 'CREATIVE_DOCUMENT', reference_only: true }];
  return { ...row, storyboard_speech: pin, parameters, source_snapshots: sources } as unknown as RecordedMediaCommand;
}
/** Optional provenance stays absent on legacy commands; present provenance is always closed and speech-only. */
export function checkedStoryboardSpeechFields(command: unknown): void {
  const row = storyboardRecord(command); if (Object.hasOwn(row, 'storyboard_speech')) checkedStoryboardSpeechCommand(row);
}
export function sameStoryboardSpeech(expected: Pick<MediaCommand, 'storyboard_speech'>, value: unknown): boolean {
  try {
    const row = storyboardRecord(value);
    if (expected.storyboard_speech === undefined) return !Object.hasOwn(row, 'storyboard_speech');
    const before = checkedStoryboardSpeechCommand(expected), after = checkedStoryboardSpeechCommand(row);
    return samePin(before.storyboard_speech!, after.storyboard_speech!) && ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'allow_cloud', 'license_note'].every(key => before[key as keyof MediaCommand] === after[key as keyof MediaCommand])
      && before.parameters.voice_id === after.parameters.voice_id && before.parameters.speech_rate === after.parameters.speech_rate;
  } catch { return false; }
}
export function checkedStoryboardSpeechSelection(receipt: StoryboardReceipt, shot: StoryboardShot, dialogueIndex: number): StoryboardSpeechPin {
  if (!receipt.approved || !receipt.shots.some(row => row.shot_id === shot.shot_id && row.shot_version === shot.shot_version && row.shot_digest === shot.shot_digest && JSON.stringify(row.shot) === JSON.stringify(shot.shot))) storyboardInvalid();
  const pin = checkedStoryboardSpeechPin({ document_snapshot: receipt.document_snapshot, shot_id: shot.shot_id, shot_version: shot.shot_version, shot_digest: shot.shot_digest, dialogue_index: dialogueIndex });
  storyboardText(shot.shot.dialogue[dialogueIndex]?.text, 16000); return pin;
}
export function checkedStoryboardAudioRequest(value: unknown, expected: StoryboardSpeechPin): StoryboardAudioRequest {
  const row = storyboardRecord(value); storyboardClosed(row, ['contract', 'shot_pin', 'command', 'automatic_dispatch', 'model_called', 'output_policy', 'product_acceptance']);
  if (row.contract !== 'studio-storyboard-audio-request/1' || row.automatic_dispatch !== false || row.model_called !== false || row.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' || row.product_acceptance !== 'LOCAL_REQUIRED') storyboardInvalid();
  const pin = checkedStoryboardSpeechPin(row.shot_pin), command = checkedStoryboardSpeechCommand(row.command);
  if (!samePin(pin, expected) || !samePin(pin, command.storyboard_speech!)) storyboardInvalid();
  return { ...row, shot_pin: pin, command } as StoryboardAudioRequest;
}
