#!/usr/bin/env node
'use strict';

const { spawn, spawnSync } = require('node:child_process');
const nodeCrypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const outputBootstrap = require('./output-bootstrap.cjs');

const LATEST_CHECK_MS = 24 * 60 * 60 * 1000;
const RETRY_CHECK_MS = 60 * 60 * 1000;
const RELEASES = path.join(
  process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache'),
  'ryugi',
  'artifacts',
);
const LATEST_FILE = path.join(RELEASES, 'latest.json');
const win32 = process.platform === 'win32';

const valid = (v) => /^\d+\.\d+\.\d+(?:[-+][0-9A-Z.-]+)?$/i.test(v || '');
const parts = (v) => v.split(/[-+]/)[0].split('.').map(Number);
const compare = (a, b) => {
  const x = parts(a),
    y = parts(b);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i];
  return 0;
};
const cliOf = (version) =>
  path.join(RELEASES, version, 'node_modules', 'ryugi-artifacts', 'dist', 'cli.cjs');
const protocolChecks = new Map();
function usesOutputProtocol(cli) {
  if (protocolChecks.has(cli)) return protocolChecks.get(cli);
  const probe = spawnSync(process.execPath, [cli, '--version', '--format', 'json'], {
    env: { ...process.env, RYUGI_NO_UPDATE_CHECK: '1' },
    encoding: 'utf8',
    timeout: 5000,
    maxBuffer: 64 * 1024,
  });
  let accepted = false;
  try {
    const value = JSON.parse(probe.stdout);
    accepted =
      probe.status === 0 &&
      value.schema === 'ryugi.cli/v1' &&
      value.command === 'version' &&
      value.outcome === 'success' &&
      Array.isArray(value.data?.capabilities) &&
      value.data.capabilities.includes('reviewBundlesV1');
  } catch {}
  protocolChecks.set(cli, accepted);
  return accepted;
}
function requireOutputProtocol(cli) {
  if (!usesOutputProtocol(cli))
    throw new LaunchError(
      `The installed CLI does not provide ryugi.cli/v1 with reviewBundlesV1. Install a current ryugi-artifacts release or rebuild the local CLI.`,
    );
}

// The local checkout has no release version. Fingerprint the code that affects
// the running server so start replaces an older process instead of reusing it.
function localVersion() {
  const hash = nodeCrypto.createHash('sha256');
  for (const name of ['cli.cjs', 'server.cjs']) {
    try {
      hash.update(`${name}\0`);
      hash.update(fs.readFileSync(path.join(__dirname, name)));
    } catch {}
  }
  return `local-${hash.digest('hex').slice(0, 12)}`;
}

class LaunchError extends Error {}

// Best effort: a sandbox with a read-only cache can still run a release that is already installed.
function record(version, checkedAt) {
  try {
    fs.mkdirSync(RELEASES, { recursive: true });
    const tmp = `${LATEST_FILE}.${process.pid}`;
    fs.writeFileSync(tmp, JSON.stringify({ version, checkedAt }));
    fs.renameSync(tmp, LATEST_FILE);
  } catch {}
}

function cachedLatest() {
  try {
    const { version, checkedAt } = JSON.parse(fs.readFileSync(LATEST_FILE, 'utf8'));
    if (
      valid(version) &&
      Date.now() - checkedAt < LATEST_CHECK_MS &&
      (!fs.existsSync(cliOf(version)) || usesOutputProtocol(cliOf(version)))
    )
      return version;
  } catch {}
  return null;
}

function newestInstalled() {
  let names = [];
  try {
    names = fs.readdirSync(RELEASES);
  } catch {}
  return (
    names
      .filter((v) => valid(v) && fs.existsSync(cliOf(v)) && usesOutputProtocol(cliOf(v)))
      .sort(compare)
      .pop() || null
  );
}

// npm is npm.cmd on Windows and needs cmd, which splits unquoted arguments on spaces (C:\Users\Jane Doe).
function npmCommand(args, windows) {
  if (!windows) return { file: 'npm', args, shell: false };
  return {
    file: ['npm', ...args.map((arg) => `"${arg.replaceAll('"', '""')}"`)].join(' '),
    args: [],
    shell: true,
  };
}

function npm(args) {
  const { file, args: argv, shell } = npmCommand(args, win32);
  return spawnSync(file, argv, { encoding: 'utf8', shell, maxBuffer: 16 * 1024 * 1024 });
}

const NEEDS_NETWORK = `network access and a writable ${RELEASES}, so rerun outside the sandbox`;

function askNpm() {
  const result = npm([
    'view',
    'ryugi-artifacts',
    'version',
    '--prefer-online',
    '--fetch-retries=0',
    '--fetch-timeout=10000',
  ]);
  const version = result.status === 0 ? (result.stdout || '').trim().split('\n').pop().trim() : '';
  return valid(version) ? version : null;
}

function fallback(reason) {
  const installed = newestInstalled();
  if (!installed) throw new LaunchError(`${reason} No cached CLI provides ryugi.cli/v1.`);
  record(installed, Date.now() - LATEST_CHECK_MS + RETRY_CHECK_MS);
  return installed;
}

function install(version) {
  if (fs.existsSync(cliOf(version))) {
    requireOutputProtocol(cliOf(version));
    return version;
  }
  const target = path.join(RELEASES, version);
  const staging = `${target}.install.${process.pid}`;
  try {
    fs.rmSync(staging, { recursive: true, force: true });
    fs.mkdirSync(staging, { recursive: true });
  } catch {
    return fallback(
      `Could not install ryugi-artifacts@${version}; the first start of each version needs ${NEEDS_NETWORK}.`,
    );
  }
  const result = npm([
    'install',
    '--prefix',
    staging,
    '--no-save',
    '--no-package-lock',
    '--no-audit',
    '--no-fund',
    '--loglevel=error',
    `ryugi-artifacts@${version}`,
  ]);
  if (
    result.status !== 0 ||
    !fs.existsSync(path.join(staging, 'node_modules', 'ryugi-artifacts', 'dist', 'cli.cjs'))
  ) {
    fs.rmSync(staging, { recursive: true, force: true });
    return fallback(
      `Could not install ryugi-artifacts@${version} from npm; the first start of each version needs ${NEEDS_NETWORK}. npm said: ${(result.stderr || result.stdout || '').trim()}`,
    );
  }
  try {
    fs.renameSync(staging, target);
  } catch {}
  fs.rmSync(staging, { recursive: true, force: true });
  if (!fs.existsSync(cliOf(version)))
    throw new LaunchError(
      `Installed ryugi-artifacts@${version} but could not move it into ${target}`,
    );
  requireOutputProtocol(cliOf(version));
  return version;
}

function resolveRelease() {
  const cached = cachedLatest();
  if (cached) return install(cached);
  const latest = askNpm();
  if (!latest)
    return fallback(
      `Could not reach npm for the latest ryugi-artifacts; the first start needs ${NEEDS_NETWORK}.`,
    );
  record(latest, Date.now());
  return install(latest);
}

function ownerPid() {
  if (win32) return null;
  const result = spawnSync('ps', ['-o', 'ppid=', '-p', String(process.ppid)], { encoding: 'utf8' });
  const parent = Number((result.stdout || '').trim());
  return Number.isInteger(parent) && parent > 1 ? parent : process.ppid;
}

function main() {
  const args = process.argv.slice(2);
  let sessionProof;
  const proofIndex = args.indexOf('--ryugi-session');
  if (proofIndex >= 0) {
    sessionProof = args[proofIndex + 1];
    if (!/^[\da-f-]{36}:[\da-f-]{36}$/i.test(sessionProof || ''))
      throw new LaunchError(
        'The Ryugi session binding is invalid. Use the launcher supplied by the current session hook.',
      );
    args.splice(proofIndex, 2);
  }
  const selection = outputBootstrap.resolveSelection(args);
  if (selection.error) {
    outputBootstrap.reportFailure(args, selection.error, selection);
    return;
  }
  const local = path.join(__dirname, 'cli.cjs');
  const env = {
    ...process.env,
    RYUGI_ARTIFACTS_COMMAND: `node "${__filename}"${sessionProof ? ` --ryugi-session ${sessionProof}` : ''}`,
  };
  let cli = local;
  if (!fs.existsSync(local)) {
    const version = resolveRelease();
    cli = cliOf(version);
    env.RYUGI_ARTIFACTS_VERSION = version;
  } else if (!env.RYUGI_ARTIFACTS_VERSION) {
    env.RYUGI_ARTIFACTS_VERSION = localVersion();
  }
  requireOutputProtocol(cli);
  let customHost = null;
  try {
    customHost = require('./custom-hosts.cjs').matchCustomHost(process.env);
  } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND')
      console.error(JSON.stringify({ type: 'comment-watch-error', message: error.message }));
  }
  let subscription = null;
  if (
    customHost ||
    sessionProof ||
    process.env.CODEX_THREAD_ID ||
    process.env.CODEX_SESSION_ID ||
    process.env.CLAUDE_CODE_SESSION_ID ||
    process.env.PI_SESSION_ID ||
    process.env.ANTIGRAVITY_CONVERSATION_ID
  ) {
    try {
      subscription = require('./comment-subscriptions.cjs').subscriptionFor(
        args,
        process.env,
        sessionProof,
      );
    } catch (error) {
      if (error.code !== 'MODULE_NOT_FOUND')
        console.error(JSON.stringify({ type: 'comment-watch-error', message: error.message }));
    }
  }
  const idx = args.indexOf('--project-dir');
  const projectDir =
    idx >= 0
      ? args[idx + 1]
      : args.find((arg) => arg.startsWith('--project-dir='))?.slice('--project-dir='.length);
  if (customHost && (subscription || args[0] === 'start')) {
    try {
      require('./cmd-comment-watch.cjs').ensureWatch(
        projectDir || process.cwd(),
        customHost,
        process.env,
      );
    } catch {}
  } else if (
    !customHost &&
    process.env.ANTIGRAVITY_CONVERSATION_ID &&
    process.env.ANTIGRAVITY_LS_ADDRESS
  ) {
    try {
      require('./agy-comment-watch.cjs').ensureWatch(projectDir || process.cwd(), process.env);
    } catch {}
  }
  const given = Number(env.RYUGI_ARTIFACTS_OWNER);
  const owner = Number.isInteger(given) && given > 1 ? given : ownerPid();
  if (owner) env.RYUGI_ARTIFACTS_OWNER = String(owner);
  const child = spawn(process.execPath, [cli, ...args], { env, stdio: 'inherit' });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
  child.on('close', async (code, signal) => {
    process.exitCode = code ?? (signal ? 1 : 0);
    if (subscription) await subscribe(subscription);
  });
}

// The hub is running only once the CLI command has returned, so the subscription follows it.
async function subscribe(subscription) {
  try {
    const { hubProjectOf, postToHub, postToServer } = require('./agent-event.cjs');
    await postToServer(hubProjectOf(subscription.project), '/api/agent/subscribe', subscription);
    const defaultHome = path.join(os.homedir(), '.ryugi', 'server');
    // The session's watcher dials the hub of the session's own environment, normally the default one, not the hub this command was pointed at.
    if (
      process.env.RYUGI_SERVER_HOME &&
      path.resolve(process.env.RYUGI_SERVER_HOME) !== defaultHome
    )
      await postToHub(
        path.join(defaultHome, 'server-info'),
        subscription.project,
        '/api/agent/subscribe',
        subscription,
      );
  } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND')
      console.error(JSON.stringify({ type: 'comment-watch-error', message: error.message }));
  }
}

// Copied on its own into installs, so it cannot require process-title.cjs.
function setLauncherTitle() {
  if (win32) return;
  const root = path.join(__dirname, '..', '..', '..');
  const version = ['package.json', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json']
    .map((file) => {
      try {
        const manifest = JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
        return manifest.name === 'ryugi' ? manifest.version || null : null;
      } catch {
        return null;
      }
    })
    .find(Boolean);
  process.title = version ? `Ryugi launcher (${version})` : 'Ryugi launcher';
}

function run() {
  setLauncherTitle();
  try {
    main();
  } catch (err) {
    outputBootstrap.reportFailure(process.argv.slice(2), err);
  }
}

if (require.main === module) run();

module.exports = { npmCommand, run };
