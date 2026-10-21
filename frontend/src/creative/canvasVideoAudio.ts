/** Reads an optional task parameter only; this grants no execution authority. */
export function checkedCanvasVideoAudioOption(parameters: unknown): boolean | undefined {
  if (parameters === null || typeof parameters !== 'object' || Array.isArray(parameters)) {
    throw new Error('STUDIO_CANVAS_VIDEO_AUDIO_OPTION_INVALID');
  }
  const field = Object.getOwnPropertyDescriptor(parameters, 'include_audio');
  if (!field) return undefined;
  if (!Object.prototype.hasOwnProperty.call(field, 'value') || typeof field.value !== 'boolean') {
    throw new Error('STUDIO_CANVAS_VIDEO_AUDIO_OPTION_INVALID');
  }
  return field.value;
}
