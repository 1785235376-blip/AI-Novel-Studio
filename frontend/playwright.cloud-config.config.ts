import { defineConfig } from '@playwright/test';
import base from './playwright.visual.config';
export default defineConfig({ ...base, testMatch: /cloud-config\.spec\.ts/, outputDir: 'test-results/cloud-config', reporter: 'list' });
