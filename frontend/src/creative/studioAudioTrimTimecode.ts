/** Source positions use the original trim owner's integer-millisecond contract. */
export function parseAudioTrimTimecode(value: string): number | null {
  const match = /^(?:(\d{1,2}):([0-5]\d):|([0-9]{1,2}):)([0-5]\d)(?:\.(\d{1,3}))?$/.exec(value.trim());
  if (!match) return null;
  const minutes = match[1] === undefined ? Number(match[3]) : Number(match[1]) * 60 + Number(match[2]);
  const result = (minutes * 60 + Number(match[4])) * 1000 + Number((match[5] || '').padEnd(3, '0'));
  return result <= 600000 ? result : null;
}

export function formatAudioTrimTimecode(value: string): string {
  if (!/^\d+$/.test(value)) return '';
  const milliseconds = Number(value);
  if (!Number.isSafeInteger(milliseconds) || milliseconds > 600000) return '';
  return `${Math.floor(milliseconds / 60000)}:${String(Math.floor(milliseconds / 1000) % 60).padStart(2, '0')}.${String(milliseconds % 1000).padStart(3, '0')}`;
}
