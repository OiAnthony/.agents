'use strict';

const { setRyugiTitle } = require('./process-title.cjs');
const { execFile, execFileSync } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {
  ensureDesktopRuntime,
  hasDesktopPipe,
  sendDesktop,
} = require('./codex-desktop-transport.cjs');
const { wakeMessage } = require('./comment-watch.cjs');
const {
  bindCodexSession,
  projectRoot,
  unbindCodexSession,
  UUID,
} = require('./comment-subscriptions.cjs');
const { matchCustomHost } = require('./custom-hosts.cjs');
const { createDeliveryQueue } = require('./delivery-queue.cjs');
const { openHubChannel } = require('./hub-channel.cjs');

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function endpoint(value) {
  if (
    typeof value !== 'string' ||
    [...value].some((char) => char.charCodeAt(0) < 33 || /\s/.test(char))
  )
    return null;
  if (value.startsWith('unix://')) return value;
  try {
    const url = new URL(value);
    return ['ws:', 'wss:'].includes(url.protocol) && !url.username && !url.password ? value : null;
  } catch {
    return null;
  }
}

// Hooks do not receive the connection URL. Follow the launching host, never another thread's env ID.
function hostEndpoint() {
  if (process.platform === 'win32') return null;
  let pid = process.ppid;
  for (let i = 0; i < 8 && pid > 1; i++) {
    try {
      const info = execFileSync('ps', ['-p', String(pid), '-o', 'ppid=,comm='], {
        encoding: 'utf8',
        timeout: 1000,
      })
        .trim()
        .match(/^(\d+)\s+(\S.*)$/);
      if (!info) return null;
      if (path.basename(info[2]).startsWith('codex')) {
        const args = execFileSync('ps', ['-p', String(pid), '-o', 'args='], {
          encoding: 'utf8',
          timeout: 1000,
        });
        const match = args.match(/--listen(?:=|\s+)(?:"([^"]+)"|'([^']+)'|(\S+))/);
        if (match) return endpoint(match[1] || match[2] || match[3]);
      }
      pid = Number(info[1]);
    } catch {
      return null;
    }
  }
  return null;
}

function cliEndpoint() {
  return endpoint(process.env.RYUGI_CODEX_REMOTE) || hostEndpoint();
}

function context(input, env = process.env) {
  // CODEX_THREAD_ID can be inherited from the process that launched this Codex session.
  if (!UUID.test(input.session_id || '') || typeof input.cwd !== 'string') return null;
  const project = projectRoot(input.cwd);
  const data =
    env.PLUGIN_DATA || env.CLAUDE_PLUGIN_DATA || path.join(project, '.ryugi/artifacts/.state');
  return {
    session: input.session_id,
    project,
    file: path.join(data, 'codex-comment-watch', 'workers', `${input.session_id}.json`),
  };
}

function alive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === 'EPERM';
  }
}

function claim(ctx) {
  fs.mkdirSync(path.dirname(ctx.file), { recursive: true });
  const state = {
    pid: process.pid,
    token: randomUUID(),
    project: ctx.project,
    session: ctx.session,
  };
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const fd = fs.openSync(ctx.file, 'wx', 0o600);
      try {
        fs.writeFileSync(fd, JSON.stringify(state));
      } finally {
        fs.closeSync(fd);
      }
      return state;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      const previous = readJson(ctx.file);
      if (alive(previous?.pid)) return null;
      try {
        // A second startup can arrive while the first writes its ownership record.
        if (!previous && Date.now() - fs.statSync(ctx.file).mtimeMs < 5000) return null;
        if (readJson(ctx.file)?.token === previous?.token) fs.rmSync(ctx.file, { force: true });
      } catch {
        // A concurrent lifecycle hook may already have removed the stale record.
      }
    }
  }
  return null;
}

function queueComment(ctx, remote, event, signal) {
  const message = wakeMessage(event);
  if (!remote) return sendDesktop(ctx, message, signal);
  const args = [
    'queue',
    '--remote',
    remote,
    '--thread',
    ctx.session,
    '--message',
    message,
    '--resume',
  ];
  const tokenEnv = process.env.RYUGI_CODEX_REMOTE_AUTH_TOKEN_ENV;
  if (tokenEnv && /^[a-z_]\w*$/i.test(tokenEnv)) args.push('--remote-auth-token-env', tokenEnv);
  return new Promise((resolve, reject) => {
    execFile(
      'codex',
      args,
      {
        cwd: ctx.project,
        env: { ...process.env, CODEX_THREAD_ID: ctx.session, CODEX_SESSION_ID: ctx.session },
        signal,
        timeout: 15000,
        maxBuffer: 16384,
      },
      (error, stdout, stderr) => {
        if (error) reject(new Error(stderr.trim() || error.message));
        // Exit 0 acknowledges durable enqueue, even when --resume prints a warning: do not enqueue twice.
        else resolve({ receipt: stdout.trim(), warning: stderr.trim() });
      },
    );
  });
}

function notice(input, message) {
  process.stdout.write(
    `${JSON.stringify({
      hookSpecificOutput: {
        hookEventName: input.hook_event_name || 'SessionStart',
        additionalContext: message,
      },
    })}\n`,
  );
}

function watch(ctx, input, remote) {
  try {
    if (matchCustomHost(process.env)) return;
  } catch {}
  const desktop = !remote && hasDesktopPipe();
  if (!desktop && !remote) {
    notice(
      input,
      'Ryugi comment watch needs the current Codex App Server endpoint. Set RYUGI_CODEX_REMOTE for a host that does not expose --listen.',
    );
    return;
  }
  const state = claim(ctx);
  if (!state) return;
  if (desktop) state.transport = 'desktop';
  else state.remote = remote;
  fs.writeFileSync(ctx.file, JSON.stringify(state), { mode: 0o600 });
  const controller = new AbortController();
  const update = (fields) => {
    if (readJson(ctx.file)?.token === state.token)
      fs.writeFileSync(ctx.file, JSON.stringify({ ...state, ...fields }), { mode: 0o600 });
  };
  let channel;
  const queue = createDeliveryQueue({
    deliver: (event) => queueComment(ctx, remote, event, controller.signal),
    delivered: (id) => channel.delivered(id),
    onSuccess: (event, { receipt, warning }) =>
      update({ artifact: event.artifact, receipt, warning, queuedAt: new Date().toISOString() }),
    onFailure: (error) => update({ lastError: String(error.message).slice(0, 800) }),
  });
  const stop = () => {
    queue.close();
    channel.close();
    controller.abort();
    if (readJson(ctx.file)?.token === state.token) fs.rmSync(ctx.file, { force: true });
    process.exit(0);
  };
  channel = openHubChannel({
    project: ctx.project,
    host: 'codex',
    session: ctx.session,
    agent: 'Codex',
    onEvent: (event, id) => queue.push(event, id),
    onRetract: (message) => queue.retract(message),
    onReplaced: stop,
  });
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
}

function stopWorker(file) {
  const worker = readJson(file);
  fs.rmSync(file, { force: true });
  if (worker?.pid !== process.pid && alive(worker?.pid))
    try {
      process.kill(worker.pid, 'SIGTERM');
    } catch {}
}

function main() {
  setRyugiTitle('watch-comments');
  if (process.argv[2] === 'watch' || process.argv[2] === 'bind') {
    try {
      if (matchCustomHost(process.env)) return;
    } catch {}
  }
  const remote = process.argv[2] === 'watch' ? cliEndpoint() : null;
  let failure = null;
  if (process.argv[2] === 'watch' && !remote)
    try {
      ensureDesktopRuntime();
    } catch (error) {
      failure = error.message;
    }
  let input;
  try {
    input = JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch {
    return;
  }
  const ctx = context(input);
  if (!ctx) return;
  if (process.argv[2] === 'stop') {
    stopWorker(ctx.file);
    unbindCodexSession(ctx.session);
  } else if (process.argv[2] === 'bind') {
    const proof = bindCodexSession(ctx.session);
    const launcher = path.join(__dirname, 'ryugi.cjs');
    notice(
      input,
      `Ryugi artifact commands for this session must use the bound launcher below. It targets this hook session even when parent session environment variables were inherited. Keep --ryugi-session in follow-up commands.\nnode ${JSON.stringify(launcher)} --ryugi-session ${proof}`,
    );
  } else if (process.argv[2] === 'watch') {
    if (failure) notice(input, failure);
    else {
      bindCodexSession(ctx.session);
      watch(ctx, input, remote);
    }
  }
}

module.exports = { context, endpoint, hostEndpoint, projectRoot };
if (require.main === module) main();
