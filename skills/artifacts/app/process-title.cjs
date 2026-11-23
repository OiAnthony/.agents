'use strict';

const fs = require('node:fs');
const path = require('node:path');

const PLUGIN_ROOT = path.join(__dirname, '..', '..', '..');
const MANIFESTS = ['package.json', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json'];

function readVersion(file) {
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(PLUGIN_ROOT, file), 'utf8'));
    return manifest.name === 'ryugi' ? manifest.version || null : null;
  } catch {
    return null;
  }
}

function setRyugiTitle(role) {
  // On Windows process.title renames the console window the user typed the command in.
  if (process.platform === 'win32') return;
  const version = MANIFESTS.map(readVersion).find(Boolean);
  process.title = version ? `Ryugi ${role} (${version})` : `Ryugi ${role}`;
}

module.exports = { setRyugiTitle };
