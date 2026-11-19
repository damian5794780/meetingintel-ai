import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../..', import.meta.url));
const localPython = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = existsSync(localPython) ? localPython : 'python';
export default defineConfig({
  testDir:'./e2e', timeout:30000, workers:1,
  use:{baseURL:process.env.E2E_BASE_URL || 'http://127.0.0.1:3000', channel:process.env.PLAYWRIGHT_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined), screenshot:'only-on-failure', trace:'retain-on-failure'},
  webServer: process.env.E2E_EXTERNAL === '1' ? undefined : [
    {command:`"${python}" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000`,cwd:root,url:'http://127.0.0.1:8000/health',timeout:30000,env:{DATABASE_PATH:'data/e2e.db',TAVILY_API_KEY:'',LLM_API_KEY:''}},
    {command:'npm run start -- --port 3000',url:'http://127.0.0.1:3000',timeout:30000},
  ],
});
