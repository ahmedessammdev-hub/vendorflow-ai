import { defineConfig } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const apiPort = 18742;
const baseURL = 'http://localhost:14426';
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 60000,
  reporter: 'list',
  use: {
    baseURL,
    channel: process.platform === 'win32' ? 'msedge' : 'chromium',
    viewport: { width: 1360, height: 960 },
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port ' + apiPort,
      cwd: '../backend',
      env: {
        DATABASE_PATH: join(tmpdir(), 'vendorflow-e2e-' + randomUUID() + '.sqlite'),
        JIRA_MODE: 'simulation',
        LLM_API_KEY: '',
        LLM_BASE_URL: '',
        LLM_MODEL: '',
      },
      url: 'http://127.0.0.1:' + apiPort + '/api/health',
      timeout: 60000,
    },
    {
      command: 'npm run start -- --port 14426',
      env: { VENDORFLOW_API_PORT: String(apiPort) },
      url: baseURL,
      timeout: 90000,
    },
  ],
});
