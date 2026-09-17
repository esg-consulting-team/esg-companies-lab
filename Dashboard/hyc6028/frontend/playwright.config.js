import { defineConfig, devices } from "@playwright/test";

// 백엔드 venv의 python 경로 (Windows 기준). 다른 OS에서 돌리려면 이 경로만 바꾸면 됩니다.
const BACKEND_PYTHON = "../backend/venv/Scripts/python.exe";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  // 테스트 실행 전 프론트/백엔드가 안 떠있으면 자동으로 띄워줍니다.
  // 이미 떠 있는 서버가 있으면 그대로 재사용합니다 (reuseExistingServer).
  webServer: [
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: `${BACKEND_PYTHON} -m uvicorn app.main:app --port 8000 --host 127.0.0.1`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
