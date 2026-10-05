import {defineConfig,devices} from '@playwright/test';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(frontend,'..');
const python=process.env.R2_PYTHON||'python';
export default defineConfig({
 testDir:path.join(frontend,'tests','e2e'),testMatch:/r2-business\.spec\.ts/,workers:1,fullyParallel:false,timeout:90000,expect:{timeout:15000},
 reporter:[['list'],['junit',{outputFile:process.env.CI_RECEIPTS?path.join(process.env.CI_RECEIPTS,'business.xml'):'test-results-r2/business.xml'}]],
 use:{baseURL:'http://127.0.0.1:5175',locale:'zh-CN',viewport:{width:1440,height:900},trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome'],launchOptions:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:undefined}}],
 webServer:[
  {command:`"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8015`,cwd:root,url:'http://127.0.0.1:8015/api/health',timeout:60000,reuseExistingServer:false,env:{STORAGE_BACKEND:'file',ENABLE_COLLABORATION_RUNTIME:'false',ENABLE_PACKAGED_RUNTIME:'false',MOCK_PROVIDER:'true',MOCK_STREAM_DELAY_MS:'0',ENABLE_CLOUD:'false',CREDENTIAL_VAULT_BACKEND:'memory',CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK:'true',FRONTEND_ORIGIN:'http://127.0.0.1:5175'}},
  {command:`"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175`,cwd:frontend,url:'http://127.0.0.1:5175',timeout:60000,reuseExistingServer:false,env:{V061_API_URL:'http://127.0.0.1:8015'}}
 ]
});
