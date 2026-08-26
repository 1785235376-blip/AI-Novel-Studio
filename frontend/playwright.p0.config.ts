import baseConfig from './playwright.config';

export default {
  ...baseConfig,
  testMatch:/p0-feature-launcher\.spec\.ts/,
};
