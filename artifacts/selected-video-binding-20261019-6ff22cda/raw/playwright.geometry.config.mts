import original from '../studio-v2-selected-video-binding/frontend/playwright.visual.config.ts';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const evidence = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(evidence, '../studio-v2-selected-video-binding/frontend');
const launchOptions = { executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' };
export default { ...original, outputDir: path.join(evidence, 'browser-geometry-results'), reporter: [['json', { outputFile: path.join(evidence, 'browser-geometry.json') }]],
  use: { ...original.use, baseURL: 'http://127.0.0.1:5188', launchOptions },
  projects: [{ name: 'chromium', use: { ...original.projects![0].use, launchOptions } }],
  webServer: { ...original.webServer, command: `"${process.execPath}" node_modules/vite/bin/vite.js --config "${path.join(evidence, 'vite.case-exact.config.mjs')}" --host 127.0.0.1 --port 5188 --strictPort`,
    cwd: frontend, url: 'http://127.0.0.1:5188/ui-fixture', reuseExistingServer: false },
};
