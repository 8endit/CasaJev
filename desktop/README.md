# CasaJev Desktop

This shell keeps the existing local Python core and replaces the screenshot-based
embedded browser with one visible, sandboxed Electron `WebContentsView`.

```bash
npm install
npm start
npm run dev
npm run package:mac
```

`npm run dev` uses the source checkout directly. Changes to Python or Electron
code restart the local development app automatically without creating a wheel,
ZIP or packaged app. Changes under `casajev/static/` reload the visible shell in
place. The persistent CasaJev state remains under the normal app user-data path.

Use `npm run package:mac` only when a new distributable release is needed.

The packaged macOS app expects `uv` on the machine. It creates its Python environment
under the app's user-data directory and stores CasaJev state separately from the app
bundle. Remote pages have no Node integration. Permissions, downloads, pop-ups and
private-network destinations are denied.
