import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './',
  fullyParallel: true,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on',
    video: 'on',
  },
  projects: [
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
