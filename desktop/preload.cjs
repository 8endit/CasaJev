const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('casajevDesktop', Object.freeze({
  active: true,
  onShowBrowser(callback) {
    if (typeof callback !== 'function') return;
    ipcRenderer.on('casajev-show-browser', (_event, conversation) => callback(conversation));
  },
  setBrowserBounds(value) {
    if (!value || typeof value !== 'object') return;
    const clean = {};
    for (const key of ['x','y','width','height']) {
      if (!Number.isFinite(value[key])) return;
      clean[key] = Math.round(value[key]);
    }
    clean.visible = value.visible === true;
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(value.conversation || '')) return;
    clean.conversation = value.conversation;
    ipcRenderer.send('casajev-browser-bounds', clean);
  }
}));
