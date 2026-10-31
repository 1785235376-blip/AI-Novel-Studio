import { describe, expect, it } from 'vitest';
import { missingAudioMeasurementLabel } from './studioAudioReceiptContext';
import { audioCommand, audioRecipe } from './studioAudioWav.testFixtures';

type Context = Parameters<typeof missingAudioMeasurementLabel>[0];
// Negative fixtures intentionally bypass DTO typing; production validators are unchanged.
type MalformedContext = { operation_id: string; command: { operation_id: string; parameters: Record<string, unknown> } | null; execution_recipe: Record<string, unknown> | null };
const malformed = (context: Context) => context as unknown as MalformedContext;
const wav = (): Context => { const command = audioCommand(); return { operation_id: 'm8.audio.trim', command, execution_recipe: audioRecipe(command) }; };
describe('missing measurement wording uses recorded format context only', () => {
  it.each(['PCM_S16LE_WAV_48000_STEREO', 'PCM_S16LE_WAV_44100_MONO'])('labels a compatible %s receipt as WAV without supplying measurements', profile => {
    const context = wav(); context.execution_recipe!.output_profile = profile;
    expect(missingAudioMeasurementLabel(context)).toBe(' WAV '); expect(context).not.toHaveProperty('media_measurement');
  });
  it.each(['FLAC_48000_STEREO', 'MP3_48000_STEREO', 'WAV', 'PCM_S16LE_WAV_48000_SURROUND', '', undefined])('keeps generic wording for an unknown or non-WAV profile %s', profile => {
    const context = wav(); context.execution_recipe!.output_profile = profile; expect(missingAudioMeasurementLabel(context)).toBe('音频');
  });
  it.each(['MP3', 'FLAC', 'WAV', undefined])('does not override explicit command format %s with a conflicting WAV recipe', format => {
    const context = wav(); malformed(context).command!.parameters.output_format = format; expect(missingAudioMeasurementLabel(context)).toBe('音频');
  });
  it.each(['command format', 'command marker', 'recipe format', 'recipe marker'] as const)('requires genuine absence of %s, including present undefined values', field => {
    const context = wav();
    if (field === 'command format') malformed(context).command!.parameters.output_format = undefined;
    else if (field === 'command marker') Object.assign(context.command!, { audio_profile: undefined });
    else if (field === 'recipe format') (context.execution_recipe!.parameters as Record<string, unknown>).output_format = undefined;
    else context.execution_recipe!.audio_profile = undefined;
    expect(missingAudioMeasurementLabel(context)).toBe('音频');
  });
  it.each(['command', 'recipe', 'job operation', 'command operation', 'recipe operation'] as const)('keeps generic wording when %s is missing or inconsistent', part => {
    const context = wav();
    if (part === 'command') malformed(context).command = null;
    else if (part === 'recipe') malformed(context).execution_recipe = null;
    else if (part === 'job operation') malformed(context).operation_id = 'm8.audio.tts';
    else if (part === 'command operation') malformed(context).command!.operation_id = 'm8.audio.tts';
    else malformed(context).execution_recipe!.operation_id = 'm8.audio.tts';
    expect(missingAudioMeasurementLabel(context)).toBe('音频');
  });
});
