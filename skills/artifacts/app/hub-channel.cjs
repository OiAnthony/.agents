'use strict';

const { spawn } = require('node:child_process');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');

const PROTOCOL = 1;
const LAUNCHER = path.resolve(__dirname, 'ryugi.cjs');
const MAX_RETRY_MS = 30000;
const START_TIMEOUT_MS = 60000;
// Ctrl-C on a foreground hub is someone stopping it; SIGTERM and SIGHUP also come from logouts and service managers.
const USER_STOPS = new Set(['stop', 'stale_pid', 'SIGINT']);
const ARTIFACT = /^(?:document|artboard|whiteboard|slides|storyboard|preview)\/[a-z0-9][a-z0-9-]*$/;

const quote = (text) => `'${text.replaceAll("'", "'\"'\"'")}'`;

const sectionFor = (event) =>
  event.type === 'ryugi-choices' ? 'groups' : event.type === 'ryugi-answers' ? 'asks' : 'threads';

const sectionFlags = (section) =>
  section === 'groups' ? ['--kind', 'choose'] : section === 'asks' ? ['--status', 'submitted'] : [];

function command(project, artifact, section = 'threads') {
  if (artifact.startsWith('preview/'))
    return `node ${quote(LAUNCHER)} preview comments --id ${artifact.slice('preview/'.length)} --project-dir ${quote(project)}`;
  const flags = sectionFlags(section)
    .map((flag) => ` ${flag}`)
    .join('');
  return `node ${quote(LAUNCHER)} comment list --section ${section}${flags} --detail --format brief --project-dir ${quote(project)} --artifact ${artifact}`;
}

function listArgv(project, artifact, section = 'threads') {
  if (artifact.startsWith('preview/'))
    return [
      LAUNCHER,
      'preview',
      'comments',
      '--id',
      artifact.slice('preview/'.length),
      '--project-dir',
      project,
    ];
  return [
    LAUNCHER,
    'comment',
    'list',
    '--section',
    section,
    ...sectionFlags(section),
    '--detail',
    '--format',
    'brief',
    '--project-dir',
    project,
    '--artifact',
    artifact,
  ];
}

function hubSocketPath(env = process.env, platform = process.platform) {
  if (env.RYUGI_HUB_SOCKET) return env.RYUGI_HUB_SOCKET;
  const home = env.RYUGI_SERVER_HOME ? path.resolve(env.RYUGI_SERVER_HOME) : null;
  const own =
    home && home !== path.join(os.homedir(), '.ryugi', 'server')
      ? `-${createHash('sha256').update(home).digest('hex').slice(0, 12)}`
      : '';
  if (platform === 'win32') return `\\\\.\\pipe\\ryugi-hub-${os.userInfo().username}${own}`;
  const runtime = env.RYUGI_RUNTIME_DIR || `/tmp/ryugi-${process.getuid ? process.getuid() : -1}`;
  return path.join(runtime, `hub${own}.sock`);
}

// Another local user who can write the socket's directory could answer in the hub's place and feed the agent commands.
function safeSocketDir(socketPath) {
  if (process.platform === 'win32') return true;
  try {
    const stat = fs.lstatSync(path.dirname(socketPath));
    return stat.isDirectory() && stat.uid === process.getuid() && (stat.mode & 0o022) === 0;
  } catch {
    return true;
  }
}

const wellFormed = (event) =>
  typeof event?.project === 'string' &&
  path.isAbsolute(event.project) &&
  typeof event.artifact === 'string' &&
  ARTIFACT.test(event.artifact);

function stoppedByUser(env) {
  const home = env.RYUGI_SERVER_HOME || path.join(os.homedir(), '.ryugi', 'server');
  try {
    return USER_STOPS.has(
      JSON.parse(fs.readFileSync(path.join(home, 'server-stopped'), 'utf8')).reason,
    );
  } catch {
    return false;
  }
}

function launchHub(project, env) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      [LAUNCHER, 'start', '--background', '--no-open', '--project-dir', project],
      { env: { ...env, RYUGI_NO_UPDATE_CHECK: '1' }, stdio: 'ignore', windowsHide: true },
    );
    const timer = setTimeout(() => child.kill(), START_TIMEOUT_MS);
    child.on('error', () => resolve());
    child.on('close', () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

function pluginVersion() {
  for (const file of ['package.json', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json']) {
    try {
      const manifest = JSON.parse(
        fs.readFileSync(path.join(__dirname, '..', '..', '..', file), 'utf8'),
      );
      if (manifest.name === 'ryugi' && manifest.version) return manifest.version;
    } catch {
      continue;
    }
  }
  return '';
}

function openHubChannel(options) {
  const env = options.env || process.env;
  const socketPath = hubSocketPath(env);
  const startHub = options.startHub || ((project) => launchHub(project, env));
  const retryMs = options.retryMs || 1000;
  const maxStartGap = Math.max(1, Math.round(MAX_RETRY_MS / retryMs));
  let startGap = 1;
  let sinceStart = Infinity;
  let socket = null;
  let timer = null;
  let closed = false;
  let starting = false;

  const decorate = (event) => ({
    ...event,
    command: command(event.project, event.artifact, sectionFor(event)),
    ...(event.type === 'ryugi-comments'
      ? {}
      : { argv: listArgv(event.project, event.artifact, sectionFor(event)) }),
  });

  // Dialling a missing socket costs nothing and a hub restarted by hand should be heard at once; only launching one backs off.
  const schedule = () => {
    if (closed) return;
    clearTimeout(timer);
    timer = setTimeout(connect, retryMs);
  };

  const start = async () => {
    if (starting) return;
    starting = true;
    try {
      await startHub(options.project);
    } finally {
      starting = false;
    }
  };

  const unreachable = async () => {
    if (closed) return;
    if (stoppedByUser(env)) options.onWaiting?.('stopped');
    else if (!fs.existsSync(path.join(options.project, '.ryugi', 'artifacts')))
      options.onWaiting?.('not-a-ryugi-project');
    else if (++sinceStart >= startGap) {
      sinceStart = 0;
      startGap = Math.min(startGap * 2, maxStartGap);
      await start();
    }
    schedule();
  };

  const receive = async (message) => {
    if (message.t === 'welcome') {
      startGap = 1;
      sinceStart = Infinity;
    } else if (message.t === 'event' && wellFormed(message.event))
      options.onEvent(decorate(message.event), message.id);
    else if (message.t === 'retract') options.onRetract?.(message);
    else if (message.t === 'bye' && message.reason === 'replaced') {
      closed = true;
      socket?.destroy();
      options.onReplaced?.();
    } else if (message.t === 'refuse') {
      socket?.destroy();
    }
  };

  function connect() {
    if (closed) return;
    if (!safeSocketDir(socketPath)) {
      options.onWaiting?.('unsafe-socket-dir');
      schedule();
      return;
    }
    let welcomed = false;
    let buffer = '';
    const current = net.connect(socketPath);
    socket = current;
    current.on('connect', () => {
      current.write(
        `${JSON.stringify({
          t: 'hello',
          protocol: PROTOCOL,
          version: options.version ?? pluginVersion(),
          host: options.host,
          session: options.session,
          agent: options.agent,
        })}\n`,
      );
    });
    current.on('data', (chunk) => {
      buffer += chunk.toString('utf8');
      for (let at = buffer.indexOf('\n'); at >= 0; at = buffer.indexOf('\n')) {
        const line = buffer.slice(0, at);
        buffer = buffer.slice(at + 1);
        let message;
        try {
          message = JSON.parse(line);
        } catch {
          continue;
        }
        if (message.t === 'welcome') welcomed = true;
        void receive(message);
      }
    });
    current.on('error', () => {});
    current.on('close', () => {
      if (socket === current) socket = null;
      if (closed) return;
      if (welcomed) schedule();
      else void unreachable();
    });
  }

  connect();

  return {
    delivered(id) {
      if (socket && !socket.destroyed) socket.write(`${JSON.stringify({ t: 'delivered', id })}\n`);
    },
    unsubscribe(done) {
      closed = true;
      clearTimeout(timer);
      if (socket && !socket.destroyed) {
        socket.end(`${JSON.stringify({ t: 'unsubscribe' })}\n`, done);
      } else {
        done?.();
      }
    },
    close() {
      closed = true;
      clearTimeout(timer);
      socket?.destroy();
    },
  };
}

module.exports = { command, hubSocketPath, listArgv, openHubChannel };
