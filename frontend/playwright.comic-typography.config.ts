import { defineConfig } from '@playwright/test';
import base from './playwright.visual.config';
export default defineConfig({ ...base, testMatch: /comic-typography\.spec\.ts/, outputDir: 'test-results/comic-typography', reporter: 'list' });
