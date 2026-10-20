import type { ProductionJob } from './studioProductionClient';

/** Expected receipt context only; this never supplies an actual measurement. */
export function missingAudioMeasurementLabel(job: Pick<ProductionJob, 'operation_id' | 'command' | 'execution_recipe'>): ' WAV ' | '音频' {
  const recipe = job.execution_recipe, command = job.command;
  const parameters = recipe?.parameters;
  if (job.operation_id !== 'm8.audio.trim' || command?.operation_id !== 'm8.audio.trim'
    || recipe?.operation_id !== 'm8.audio.trim' || typeof recipe.output_profile !== 'string'
    || !/^PCM_S16LE_WAV_\d+_(?:MONO|STEREO)$/.test(recipe.output_profile)
    || !parameters || typeof parameters !== 'object' || Array.isArray(parameters)
    || Object.hasOwn(command.parameters, 'output_format') || Object.hasOwn(command, 'audio_profile')
    || Object.hasOwn(parameters, 'output_format') || Object.hasOwn(recipe, 'audio_profile')) return '音频';
  return ' WAV ';
}
