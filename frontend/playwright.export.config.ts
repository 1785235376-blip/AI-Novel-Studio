import {defineConfig,devices} from '@playwright/test';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const frontend=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(frontend,'..');
export default defineConfig({outputDir:path.join(frontend,"test-results","export"),
  testDir:path.join(frontend,'tests/e2e'),testMatch:/export-recovery\.spec\.ts/,workers:1,fullyParallel:false,timeout:60000,
  reporter:'list',use:{baseURL:'http://127.0.0.1:5178',trace:'retain-on-failure',locale:'zh-CN',timezoneId:'UTC',acceptDownloads:true},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
  webServer:[
    {command:`"${process.env.PYTHON||'python3'}" -m uvicorn export_recovery_server:app --app-dir tests/e2e --host 127.0.0.1 --port 8018`,cwd:root,url:'http://127.0.0.1:8018/health',reuseExistingServer:false},
    {command:`"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5178`,cwd:frontend,env:{V061_API_URL:'http://127.0.0.1:8018'},url:'http://127.0.0.1:5178/tests/e2e/export-recovery.html',reuseExistingServer:false},
  ],
});
