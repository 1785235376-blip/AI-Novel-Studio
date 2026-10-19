// Validation adapter only: reproduce exact Git filenames on this case-insensitive host.
// Does not change assertions, application source, OS settings, or default production config.
import original from '../studio-v2-selected-video-binding/frontend/vite.config.ts';
import fs from 'node:fs';
import path from 'node:path';
const entries = new Map();
function exactFile(file) {
  try {
    const dir = path.dirname(file);
    if (!entries.has(dir)) entries.set(dir, new Set(fs.readdirSync(dir)));
    return entries.get(dir).has(path.basename(file)) && fs.statSync(file).isFile();
  } catch { return false; }
}
export default { ...original, plugins: [{ name: 'validation-exact-git-filenames', enforce: 'pre',
  resolveId(source, importer) {
    if (!importer || !source.startsWith('.') || source.includes('?') || importer.includes('node_modules')) return null;
    const base = path.resolve(path.dirname(importer.split('?')[0]), source);
    const extensions = ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json'];
    const file = [base, ...extensions.map(ext => base + ext), ...extensions.map(ext => path.join(base, 'index' + ext))].find(exactFile);
    return file ? file.replaceAll('\\', '/') : null;
  },
}, ...original.plugins] };
