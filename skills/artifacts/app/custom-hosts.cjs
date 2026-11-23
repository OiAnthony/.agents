'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const HOST_NAME = /^[a-z][a-z0-9_-]{0,31}$/;
const SESSION_ID = /^(?!\.\.?$)(?!.*\.\.)[\w.:-]{1,128}$/;
const ENV_NAME = /^[a-z_]\w*$/i;
const BUILTIN_HOSTS = new Set(['codex', 'claude', 'pi', 'antigravity']);
const DEFAULT_TIMEOUT_MS = 15000;
const MIN_TIMEOUT_MS = 1000;
const MAX_TIMEOUT_MS = 120000;

// Custom host commands are executable code; only read the user's own config, never a project repo's .ryugi/config.json.
function configFile(env = process.env, platform = process.platform, home = os.homedir()) {
  if (typeof env.RYUGI_HOSTS_CONFIG === 'string' && env.RYUGI_HOSTS_CONFIG.trim())
    return path.resolve(env.RYUGI_HOSTS_CONFIG.trim());
  if (platform === 'win32' && env.APPDATA) return path.join(env.APPDATA, 'ryugi', 'config.json');
  return path.join(env.XDG_CONFIG_HOME || path.join(home, '.config'), 'ryugi', 'config.json');
}

function parseCommand(raw) {
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    return trimmed ? [trimmed] : null;
  }
  if (!Array.isArray(raw) || raw.length === 0) return null;
  if (!raw.every((part) => typeof part === 'string')) return null;
  const bin = raw[0].trim();
  if (!bin) return null;
  return [bin, ...raw.slice(1)];
}

function parseTimeout(raw) {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return DEFAULT_TIMEOUT_MS;
  return Math.max(MIN_TIMEOUT_MS, Math.min(MAX_TIMEOUT_MS, Math.round(raw)));
}

function loadCustomHosts(env = process.env, platform = process.platform, home = os.homedir()) {
  const file = configFile(env, platform, home);
  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return [];
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return [];
  const hosts = raw.hosts;
  if (!hosts || typeof hosts !== 'object' || Array.isArray(hosts)) return [];
  const result = [];
  for (const [name, entry] of Object.entries(hosts)) {
    if (!HOST_NAME.test(name) || BUILTIN_HOSTS.has(name)) continue;
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue;
    if (typeof entry.env !== 'string' || !ENV_NAME.test(entry.env)) continue;
    const command = parseCommand(entry.command);
    if (!command) continue;
    const agent = typeof entry.agent === 'string' && entry.agent.trim() ? entry.agent.trim() : name;
    result.push({
      host: name,
      env: entry.env,
      agent,
      command,
      timeoutMs: parseTimeout(entry.timeoutMs),
    });
  }
  return result;
}

function matchCustomHosts(env = process.env, platform = process.platform, home = os.homedir()) {
  const matches = [];
  for (const host of loadCustomHosts(env, platform, home)) {
    const value = env[host.env];
    if (typeof value === 'string' && SESSION_ID.test(value))
      matches.push({ ...host, session: value });
  }
  return matches;
}

function matchCustomHost(env = process.env, platform = process.platform, home = os.homedir()) {
  const matches = matchCustomHosts(env, platform, home);
  if (matches.length === 0) return null;
  if (matches.length === 1) return matches[0];
  throw new Error('Artifact feedback has ambiguous custom host session markers.');
}

module.exports = {
  BUILTIN_HOSTS,
  configFile,
  DEFAULT_TIMEOUT_MS,
  ENV_NAME,
  HOST_NAME,
  loadCustomHosts,
  matchCustomHost,
  matchCustomHosts,
  SESSION_ID,
};
