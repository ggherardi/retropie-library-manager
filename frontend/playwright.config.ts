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
    baseURL: "http://127.0.0.1:18001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${python}" -m uvicorn e2e_app:app --app-dir ../tests --host 127.0.0.1 --port 18001`,
    url: "http://127.0.0.1:18001/api/health",
    reuseExistingServer: false,
    env: { RLM_DATA_DIR: path.resolve("../.runtime/e2e-data") },
  },
});
