import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir:'./e2e', timeout:90000, workers:1,
  use:{ baseURL:process.env.MED_TRANSCRIPT_TEST_URL||'http://127.0.0.1:8001', headless:true,
    channel:process.env.PLAYWRIGHT_CHANNEL||'chrome', viewport:{width:1440,height:1000}, screenshot:'only-on-failure', trace:'retain-on-failure' },
  outputDir:'../../data/browser-test-results', reporter:'list' });
