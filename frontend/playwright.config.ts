import { defineConfig } from "@playwright/test";
import path from "node:path";

const python =
  process.platform === "win32"
    ? "../.venv/Scripts/python.exe"
    : "../.venv/bin/python";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${python}" -m uvicorn backend.main:app --app-dir .. --host 127.0.0.1 --port 8000`,
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: false,
    env: { RLM_DATA_DIR: path.resolve("../.runtime/e2e-data") },
  },
});
