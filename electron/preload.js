"use strict";
/**
 * electron/preload.js
 *
 * Minimal preload script with contextIsolation enabled.
 * The web UI is served by the local FastAPI server and does not need
 * direct access to Node.js APIs, so this preload exposes nothing.
 */

const { contextBridge } = require("electron");

// Expose a minimal API surface to the renderer if ever needed.
// For now the UI talks directly to the FastAPI server via fetch().
contextBridge.exposeInMainWorld("__miktos__", {
  version: process.env.npm_package_version || "0.1.0",
});
