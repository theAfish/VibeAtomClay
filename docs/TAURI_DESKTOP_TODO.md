# Tauri Desktop Packaging TODO

Use this checklist to wrap the existing Vite frontend into a native Tauri shell and ship installers. All commands are run from `packages/frontend` unless noted.

## 1) Prereqs
- [ ] Install Rust toolchain (stable) and keep it on PATH: https://rustup.rs
- [ ] Install Node.js 18+.
- [ ] Install Tauri CLI locally: `npm install -D @tauri-apps/cli`
- [ ] (If bundling backend) Have a reproducible build of the Python middleware/server via PyInstaller or similar.

## 2) Add Tauri scaffold
- [ ] From `packages/frontend`, run `npx tauri init --ci`.
- [ ] Choose `dist` as the production build folder and `http://localhost:5173` as the dev server URL.
- [ ] Verify `src-tauri/tauri.conf.json` has `distDir` pointing to `../dist` and `devPath` pointing to the Vite dev server.
- [ ] Add `"tauri"` script to `package.json`: `tauri dev` and `tauri build`.

## 3) Dev flow
- [ ] Run `npm run dev` to serve Vite, and in another shell run `npm run tauri dev` to open the native window hitting the dev server.
- [ ] Adjust window defaults in `src-tauri/tauri.conf.json` (title, size, resizable, drag regions, etc.).

## 4) Production build
- [ ] Build frontend: `npm run build` (outputs `dist/`).
- [ ] Build desktop app: `npm run tauri build` (creates `.exe/.msi` on Windows, `.dmg` on macOS, AppImage/deb/rpm on Linux).
- [ ] Test the installer output in a clean VM/user profile.

## 5) Ship the Python backend (if needed)
- [ ] Package middleware/server with PyInstaller (one-folder mode is safest). Target output folder: `dist/backend/`.
- [ ] Add the packaged backend folder to `tauri.conf.json > bundle > resources` so it is bundled next to the app.
- [ ] In `src-tauri/src/main.rs`, spawn the backend binary on app launch and kill it on exit; log stdout/stderr to a file in `AppData`/`~/.local/share`.
- [ ] Pass config/env to the backend via CLI flags or by copying default `.env` into a writable app data dir on first run.

## 6) Updates and signing
- [ ] Decide on update story: Tauri updater (requires server-hosted JSON + artifacts) or manual releases.
- [ ] Set up code signing for Windows (EV cert recommended) and macOS (Developer ID + notarization) before distributing broadly.

## 7) QA checklist
- [ ] Launch without network and ensure backend start/stop is robust.
- [ ] Verify app data paths (logs, downloads) are writable and not inside the install directory.
- [ ] Exercise install/uninstall; confirm Start Menu/Desktop shortcuts work on Windows.
- [ ] Smoke-test on macOS and a popular Linux distro if those are targets.
