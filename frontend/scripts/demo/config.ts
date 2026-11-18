import { defineConfig } from '@playwright/test';
import base from '../../playwright.config';
import { resolve } from 'node:path';
const front = resolve(import.meta.dirname, '../..');
const shared = 'default' in base ? base.default as typeof base : base;
const servers = Array.isArray(shared.webServer) ? shared.webServer : [];
export default defineConfig({
  ...shared,
  testDir: import.meta.dirname,
  testMatch: 'walkthrough.spec.ts',
  timeout: 180000,
  use: { ...shared.use, viewport: { width: 1440, height: 900 } },
  webServer: servers.map((s, i) => ({ ...s, cwd: i === 0 ? resolve(front, '../backend') : front })),
});
