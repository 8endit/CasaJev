const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const desktop = __dirname;
const project = path.resolve(desktop, '..');
const electron = path.join(desktop, 'node_modules', '.bin', 'electron');
let child = null;
let restarting = false;
let timer = null;

function start() {
  child = spawn(electron, ['.'], {
    cwd: desktop,
    env: {...process.env, CASAJEV_DEV_HOT: '1'},
    stdio: 'inherit',
  });
  child.on('exit', code => {
    child = null;
    if (restarting) {
      restarting = false;
      start();
    } else if (code && code !== 0) {
      process.exitCode = code;
    }
  });
}

function relevant(name) {
  if (!name) return false;
  const normalized = String(name).replaceAll('\\', '/');
  if (normalized.includes('__pycache__') || normalized.endsWith('.pyc') ||
      normalized.includes('node_modules/') || normalized.includes('dist-desktop/')) return false;
  return normalized.endsWith('.py') || normalized.endsWith('.cjs');
}

function restart(label) {
  clearTimeout(timer);
  timer = setTimeout(() => {
    if (!child || restarting) return;
    restarting = true;
    process.stdout.write(`\nCasaJev Dev: ${label} geändert – starte ohne Build neu.\n`);
    child.kill('SIGTERM');
  }, 300);
}

for (const root of [path.join(project, 'casajev'), desktop]) {
  fs.watch(root, {recursive: true}, (_event, name) => {
    if (relevant(name)) restart(path.relative(project, path.join(root, String(name))));
  });
}

for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  if (child) child.kill('SIGTERM');
  process.exit(0);
});

start();
