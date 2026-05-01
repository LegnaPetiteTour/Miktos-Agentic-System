"use strict";
/**
 * electron/main.js — Miktos Desktop App main process
 *
 * Lifecycle:
 *   1. Resolve miktos-server binary path (packaged vs dev).
 *   2. Set MIKTOS_DATA_DIR to ~/Library/Application Support/Miktos.
 *   3. Spawn miktos-server.
 *   4. Poll http://localhost:8000/ up to 30 times (500ms intervals).
 *   5. Show BrowserWindow once the server is ready.
 *   6. Show a loading window while waiting.
 *   7. Kill the server process on app quit.
 *   8. Add a system Tray icon with a Quit item.
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, shell } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SERVER_URL = "http://127.0.0.1:8000";
const POLL_INTERVAL_MS = 500;
const POLL_MAX_ATTEMPTS = 60; // 30 seconds total

let serverProcess = null;
let mainWindow = null;
let loadingWindow = null;
let tray = null;

// ---------------------------------------------------------------------------
// Resolve the miktos-server binary
// ---------------------------------------------------------------------------

function resolveServerBinary() {
  if (app.isPackaged) {
    // In the .app bundle, extraResources lands in process.resourcesPath
    const bin = path.join(process.resourcesPath, "miktos-server");
    if (fs.existsSync(bin)) return bin;
    throw new Error(`miktos-server not found at ${bin}`);
  }
  // Dev: look for dist/miktos-server relative to the repo root
  const devBin = path.join(__dirname, "..", "dist", "miktos-server");
  if (fs.existsSync(devBin)) return devBin;
  throw new Error(
    `miktos-server not found at ${devBin}. Run: python scripts/build_server.py`
  );
}

// ---------------------------------------------------------------------------
// Spawn the Python server
// ---------------------------------------------------------------------------

function startServer() {
  const bin = resolveServerBinary();
  const dataDir = path.join(app.getPath("appData"), "Miktos");

  console.log(`[main] Starting server: ${bin}`);
  console.log(`[main] MIKTOS_DATA_DIR: ${dataDir}`);

  serverProcess = spawn(bin, [], {
    env: {
      ...process.env,
      MIKTOS_DATA_DIR: dataDir,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  serverProcess.stdout.on("data", (d) => process.stdout.write(`[server] ${d}`));
  serverProcess.stderr.on("data", (d) => process.stderr.write(`[server] ${d}`));

  serverProcess.on("exit", (code, signal) => {
    console.log(`[main] Server exited: code=${code} signal=${signal}`);
    serverProcess = null;
  });
}

// ---------------------------------------------------------------------------
// Poll until the server responds on /
// ---------------------------------------------------------------------------

function pollServer(attempt, resolve, reject) {
  if (attempt >= POLL_MAX_ATTEMPTS) {
    reject(new Error(`Server did not start after ${POLL_MAX_ATTEMPTS} attempts`));
    return;
  }
  const req = http.get(`${SERVER_URL}/`, (res) => {
    resolve();
  });
  req.on("error", () => {
    setTimeout(() => pollServer(attempt + 1, resolve, reject), POLL_INTERVAL_MS);
  });
  req.setTimeout(400, () => {
    req.destroy();
    setTimeout(() => pollServer(attempt + 1, resolve, reject), POLL_INTERVAL_MS);
  });
}

function waitForServer() {
  return new Promise((resolve, reject) => pollServer(0, resolve, reject));
}

// ---------------------------------------------------------------------------
// Windows
// ---------------------------------------------------------------------------

function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width: 400,
    height: 220,
    resizable: false,
    frame: false,
    alwaysOnTop: true,
    webPreferences: { contextIsolation: true },
  });
  // Inline loading HTML — no external file needed
  loadingWindow.loadURL(
    "data:text/html;charset=utf-8," +
      encodeURIComponent(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {
          font-family: -apple-system, sans-serif;
          background: #1a1a2e; color: #e0e0e0;
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          height: 100vh; margin: 0;
          -webkit-app-region: drag;
        }
        h2 { margin: 0 0 12px; font-size: 1.4rem; }
        p  { margin: 0; font-size: 0.85rem; opacity: 0.6; }
      </style>
    </head>
    <body>
      <h2>Miktos</h2>
      <p>Starting server…</p>
    </body>
    </html>
  `)
  );
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: "Miktos",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Open external links in the default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://127.0.0.1:8000")) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// Tray
// ---------------------------------------------------------------------------

function createTray() {
  // Use a blank 16x16 template image; replace build/tray-icon.png if available
  const iconPath = path.join(__dirname, "build", "tray-icon.png");
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty();

  tray = new Tray(icon);
  tray.setToolTip("Miktos");
  const menu = Menu.buildFromTemplate([
    {
      label: "Open Miktos",
      click: () => {
        if (mainWindow) mainWindow.show();
        else createAndShowMain();
      },
    },
    { type: "separator" },
    { label: "Quit", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
  tray.on("double-click", () => {
    if (mainWindow) mainWindow.show();
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

async function createAndShowMain() {
  createMainWindow();
  await mainWindow.loadURL(SERVER_URL);
  mainWindow.show();
  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.close();
    loadingWindow = null;
  }
}

app.whenReady().then(async () => {
  // macOS: hide from dock while loading (re-shown when window opens)
  if (process.platform === "darwin" && app.dock) app.dock.hide();

  createLoadingWindow();

  try {
    startServer();
    await waitForServer();
  } catch (err) {
    console.error("[main] Server failed to start:", err.message);
    app.quit();
    return;
  }

  if (process.platform === "darwin" && app.dock) app.dock.show();
  createTray();
  await createAndShowMain();
});

app.on("window-all-closed", () => {
  // On macOS keep app alive in tray
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (mainWindow === null) createAndShowMain().catch(console.error);
  else mainWindow.show();
});

app.on("before-quit", () => {
  if (serverProcess) {
    console.log("[main] Killing server process...");
    serverProcess.kill("SIGINT");
    serverProcess = null;
  }
});
