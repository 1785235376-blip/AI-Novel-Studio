import { defineConfig } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import base from './playwright.visual.config';
const evidence=process.env.NLE_CUT_NAVIGATION_EVIDENCE_DIR;
if(!evidence)throw new Error('NLE_CUT_NAVIGATION_EVIDENCE_DIR must point to the task-private real runtime');
const ports=JSON.parse(readFileSync(path.join(evidence,'runtime-ports.json'),'utf8'));
export default defineConfig({...base,testMatch:/nle-cut-navigation-live\.spec\.ts/,timeout:120_000,
 outputDir:'test-results/nle-cut-navigation-live',reporter:'list',webServer:undefined,
 use:{...base.use,baseURL:`http://127.0.0.1:${ports.frontend}`,trace:'off',launchOptions:{args:['--disable-gpu']}}});
