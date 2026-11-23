'use strict';

const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createDeliveryQueue } = require('./delivery-queue.cjs');
const { openHubChannel } = require('./hub-channel.cjs');
const { wakeMessage } = require('./comment-watch.cjs');
const { projectRoot } = require('./comment-subscriptions.cjs');
const {
  DEFAULT_TIMEOUT_MS,
  HOST_NAME,
  loadCustomHosts,
  matchCustomHost,
  SESSION_ID,
} = require('./custom-hosts.cjs');

const UNSUBSCRIBE_EXIT_CODE = 10;
const MAX_OUTPUT_BYTES = 64 * 1024;

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
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

function workerFile(host, session, env = process.env) {
  const base =
    env.PLUGIN_DATA || path.join(env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache'), 'ryugi');
  return path.join(
    base,
    'cmd-comment-watch',
    'workers',
    host,
    `${encodeURIComponent(session)}.json`,
  );
}

function commandKeyOf({ command, agent, timeoutMs }) {
  return JSON.stringify({ command, agent, timeoutMs });
}

function context(input, env = process.env) {
  let host = typeof input?.host === 'string' && HOST_NAME.test(input.host) ? input.host : null;
  let session =
    typeof input?.session === 'string' && SESSION_ID.test(input.session) ? input.session : null;
  let command =
    Array.isArray(input?.command) &&
    input.command.length > 0 &&
    input.command.every((part) => typeof part === 'string') &&
    input.command[0].trim()
      ? input.command
      : null;
  let agent = typeof input?.agent === 'string' && input.agent.trim() ? input.agent.trim() : null;
  let timeoutMs =
    typeof input?.timeoutMs === 'number' && Number.isFinite(input.timeoutMs)
      ? input.timeoutMs
      : null;

  if (!host || !session || !command) {
    let matched = null;
    if (host) {
      const configured = loadCustomHosts(env).find((item) => item.host === host);
      if (configured) {
        const envSession = env[configured.env];
        matched = {
          ...configured,
          session:
            session ||
            (typeof envSession === 'string' && SESSION_ID.test(envSession) ? envSession : null),
        };
      }
    } else {
      try {
        matched = matchCustomHost(env);
      } catch {
        return null;
      }
    }
    if (matched) {
      host = host || matched.host;
      session = session || matched.session;
      command = command || matched.command;
      agent = agent || matched.agent;
      timeoutMs = timeoutMs ?? matched.timeoutMs;
    }
  }

  if (!host || !session) return null;
  const rawCwd =
    typeof input?.project === 'string' && input.project
      ? input.project
      : typeof input?.cwd === 'string' && input.cwd
        ? input.cwd
        : process.cwd();
  let project;
  try {
    project = projectRoot(rawCwd);
  } catch {
    project = path.resolve(rawCwd);
  }
  const resolvedAgent = agent || host;
  const resolvedTimeout = timeoutMs ?? DEFAULT_TIMEOUT_MS;
  return {
    host,
    session,
    project,
    command,
    agent: resolvedAgent,
    timeoutMs: resolvedTimeout,
    commandKey: command
      ? commandKeyOf({ command, agent: resolvedAgent, timeoutMs: resolvedTimeout })
      : '',
    file: workerFile(host, session, env),
  };
}

function claim(ctx) {
  fs.mkdirSync(path.dirname(ctx.file), { recursive: true });
  const state = {
    pid: process.pid,
    token: randomUUID(),
    host: ctx.host,
    session: ctx.session,
    project: ctx.project,
    commandKey: ctx.commandKey,
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
      if (alive(previous?.pid)) {
        if (previous.commandKey && ctx.commandKey && previous.commandKey !== ctx.commandKey) {
          try {
            if (readJson(ctx.file)?.token === previous.token) fs.rmSync(ctx.file, { force: true });
            process.kill(previous.pid, 'SIGTERM');
          } catch {}
          continue;
        }
        return null;
      }
      try {
        if (!previous && Date.now() - fs.statSync(ctx.file).mtimeMs < 5000) return null;
        if (readJson(ctx.file)?.token === previous?.token) fs.rmSync(ctx.file, { force: true });
      } catch {}
    }
  }
  return null;
}

function parseReceipt(stdout) {
  const trimmed = stdout.trim();
  if (!trimmed) return null;
  const candidates = [trimmed];
  const lastLine = trimmed.split('\n').pop()?.trim();
  if (lastLine && lastLine !== trimmed) candidates.push(lastLine);
  for (const text of candidates) {
    if (!text.startsWith('{') || !text.endsWith('}')) continue;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
    } catch {}
  }
  return null;
}

function deliverComment(ctx, event, signal) {
  const message = wakeMessage(event);
  const payload = JSON.stringify({
    protocol: 1,
    host: ctx.host,
    session: ctx.session,
    project: event.project || ctx.project,
    artifact: event.artifact,
    type: event.type,
    wakeMessage: message,
    event,
  });

  return new Promise((resolve, reject) => {
    const [bin, ...args] = ctx.command;
    const child = spawn(bin, args, {
      cwd: event.project || ctx.project,
      env: {
        ...process.env,
        RYUGI_HOST: ctx.host,
        RYUGI_SESSION: ctx.session,
        RYUGI_PROJECT: event.project || ctx.project,
        RYUGI_ARTIFACT: event.artifact,
        RYUGI_EVENT_TYPE: event.type,
      },
      shell: false,
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';
    let timedOut = false;
    let settled = false;

    const finish = (fn, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
      fn(value);
    };

    const killChild = () => {
      try {
        child.kill('SIGTERM');
      } catch {}
    };

    const onAbort = () => {
      killChild();
      finish(reject, new Error('Delivery aborted'));
    };

    if (signal?.aborted) {
      onAbort();
      return;
    }
    signal?.addEventListener('abort', onAbort, { once: true });

    const timer = setTimeout(() => {
      timedOut = true;
      killChild();
    }, ctx.timeoutMs);

    child.stdout.on('data', (chunk) => {
      if (stdout.length < MAX_OUTPUT_BYTES)
        stdout += chunk.toString('utf8').slice(0, MAX_OUTPUT_BYTES - stdout.length);
    });
    child.stderr.on('data', (chunk) => {
      if (stderr.length < MAX_OUTPUT_BYTES)
        stderr += chunk.toString('utf8').slice(0, MAX_OUTPUT_BYTES - stderr.length);
    });
    child.stdin.on('error', () => {});
    child.stdin.end(payload);

    child.on('error', (error) => finish(reject, error));
    child.on('close', (code, termSignal) => {
      if (timedOut) {
        return finish(reject, new Error(`Delivery command timed out after ${ctx.timeoutMs}ms`));
      }
      const parsed = parseReceipt(stdout);
      const status = typeof parsed?.status === 'string' ? parsed.status.toLowerCase() : null;
      if (code === UNSUBSCRIBE_EXIT_CODE || status === 'unsubscribe') {
        return finish(resolve, {
          action: 'unsubscribe',
          receipt: stdout.trim(),
          status: status || 'unsubscribe',
        });
      }
      if (status === 'retry') {
        return finish(
          reject,
          new Error(
            (typeof parsed?.reason === 'string' && parsed.reason) ||
              stderr.trim() ||
              'Delivery command requested retry',
          ),
        );
      }
      if (code === 0) {
        return finish(resolve, {
          action: 'delivered',
          receipt: stdout.trim(),
          status: status || 'delivered',
        });
      }
      const detail = stderr.trim() || stdout.trim();
      finish(
        reject,
        new Error(
          detail ||
            (termSignal
              ? `Delivery command killed by ${termSignal}`
              : `Delivery command exited with code ${code}`),
        ),
      );
    });
  });
}

function watch(ctx) {
  if (!ctx.command) return;
  const state = claim(ctx);
  if (!state) return;
  const controller = new AbortController();
  const update = (fields) => {
    if (readJson(ctx.file)?.token === state.token)
      fs.writeFileSync(ctx.file, JSON.stringify({ ...state, ...fields }), { mode: 0o600 });
  };
  let channel;
  let stopping = false;
  const cleanupFile = () => {
    if (readJson(ctx.file)?.token === state.token) fs.rmSync(ctx.file, { force: true });
  };
  const stop = () => {
    if (stopping) return;
    stopping = true;
    queue.close();
    channel.close();
    controller.abort();
    cleanupFile();
    process.exit(0);
  };
  const unsubscribeAndStop = () => {
    if (stopping) return;
    stopping = true;
    queue.close();
    controller.abort();
    cleanupFile();
    channel.unsubscribe(() => process.exit(0));
    setTimeout(() => process.exit(0), 1000).unref();
  };
  const queue = createDeliveryQueue({
    baseMs: 500,
    deliver: async (event) => {
      const result = await deliverComment(ctx, event, controller.signal);
      if (result.action === 'unsubscribe') {
        unsubscribeAndStop();
        return result;
      }
      return result;
    },
    delivered: (id) => {
      if (!stopping) channel.delivered(id);
    },
    onSuccess: (event, { receipt, status }) => {
      if (!stopping)
        update({
          artifact: event.artifact,
          receipt: receipt.slice(0, 800),
          status,
          queuedAt: new Date().toISOString(),
        });
    },
    onFailure: (error) => {
      if (!stopping) update({ lastError: String(error.message).slice(0, 800) });
    },
  });
  channel = openHubChannel({
    project: ctx.project,
    host: ctx.host,
    session: ctx.session,
    agent: ctx.agent,
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

function ensureWatch(project, hostConfig, env = process.env) {
  if (!hostConfig?.host || !hostConfig?.session || !hostConfig?.command) return false;
  let root;
  try {
    root = projectRoot(project || process.cwd());
  } catch {
    root = path.resolve(project || process.cwd());
  }
  const commandKey = commandKeyOf(hostConfig);
  const existing = readJson(workerFile(hostConfig.host, hostConfig.session, env));
  if (alive(existing?.pid) && existing?.commandKey === commandKey) return false;
  const child = spawn(process.execPath, [__filename, 'watch'], {
    cwd: root,
    env: { ...env },
    detached: true,
    stdio: ['pipe', 'ignore', 'ignore'],
    windowsHide: true,
  });
  child.stdin.end(
    JSON.stringify({
      host: hostConfig.host,
      session: hostConfig.session,
      project: root,
      command: hostConfig.command,
      agent: hostConfig.agent,
      timeoutMs: hostConfig.timeoutMs,
    }),
  );
  child.unref();
  return true;
}

function main() {
  let input = {};
  try {
    input = JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch {}
  const ctx = context(input);
  if (!ctx) return;
  if (process.argv[2] === 'stop') {
    stopWorker(ctx.file);
  } else if (process.argv[2] === 'watch') {
    watch(ctx);
  }
}

module.exports = {
  context,
  deliverComment,
  ensureWatch,
  parseReceipt,
  UNSUBSCRIBE_EXIT_CODE,
  workerFile,
};
if (require.main === module) {
  require('./process-title.cjs').setRyugiTitle('watch-comments');
  main();
}
