'use strict';

const { setRyugiTitle } = require('./process-title.cjs');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { wakeMessage } = require('./comment-watch.cjs');
const { projectRoot, UUID } = require('./comment-subscriptions.cjs');
const { createDeliveryQueue } = require('./delivery-queue.cjs');
const { openHubChannel } = require('./hub-channel.cjs');

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

function context(input, env = process.env) {
  const session =
    typeof input?.conversationId === 'string' && UUID.test(input.conversationId)
      ? input.conversationId
      : typeof input?.session_id === 'string' && UUID.test(input.session_id)
        ? input.session_id
        : UUID.test(env.ANTIGRAVITY_CONVERSATION_ID || '')
          ? env.ANTIGRAVITY_CONVERSATION_ID
          : null;
  const rawCwd =
    typeof input?.cwd === 'string' && input.cwd
      ? input.cwd
      : Array.isArray(input?.workspacePaths) && typeof input.workspacePaths[0] === 'string'
        ? input.workspacePaths[0]
        : process.cwd();
  if (!session || typeof rawCwd !== 'string') return null;
  let project;
  try {
    project = projectRoot(rawCwd);
  } catch {
    return null;
  }
  const data = env.PLUGIN_DATA || path.join(project, '.ryugi/artifacts/.state');
  return {
    session,
    project,
    lsAddress: env.ANTIGRAVITY_LS_ADDRESS || '',
    csrfToken: env.ANTIGRAVITY_CSRF_TOKEN || '',
    file: path.join(data, 'agy-comment-watch', 'workers', `${session}.json`),
  };
}

function claim(ctx) {
  fs.mkdirSync(path.dirname(ctx.file), { recursive: true });
  const state = {
    pid: process.pid,
    token: randomUUID(),
    project: ctx.project,
    session: ctx.session,
    lsAddress: ctx.lsAddress,
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
        if (previous.lsAddress && ctx.lsAddress && previous.lsAddress !== ctx.lsAddress) {
          try {
            if (readJson(ctx.file)?.token === previous?.token) fs.rmSync(ctx.file, { force: true });
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

function lsRpc(lsAddress, csrfToken, method, payload, signal) {
  return new Promise((resolve, reject) => {
    let url;
    try {
      const base =
        lsAddress.startsWith('http://') || lsAddress.startsWith('https://')
          ? lsAddress
          : `http://${lsAddress}`;
      url = new URL(`/exa.language_server_pb.LanguageServerService/${method}`, base);
    } catch (err) {
      reject(err);
      return;
    }
    const body = JSON.stringify(payload);
    const req = http.request(
      {
        hostname: url.hostname === 'localhost' ? '127.0.0.1' : url.hostname,
        port: url.port,
        path: url.pathname,
        method: 'POST',
        signal,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
          ...(csrfToken ? { 'x-codeium-csrf-token': csrfToken } : {}),
        },
        timeout: 5000,
      },
      (res) => {
        let out = '';
        res.on('data', (chunk) => (out += chunk));
        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            resolve({ status: res.statusCode, body: out });
          } else {
            const err = new Error(`LS RPC ${method} HTTP ${res.statusCode}: ${out.slice(0, 200)}`);
            err.statusCode = res.statusCode;
            reject(err);
          }
        });
      },
    );
    req.on('timeout', () => {
      req.destroy(new Error(`LS RPC ${method} timed out`));
    });
    req.on('error', reject);
    req.end(body);
  });
}

async function deliverComment(ctx, event, signal) {
  if (!ctx.lsAddress) throw new Error('ANTIGRAVITY_LS_ADDRESS is not set');
  const message = wakeMessage(event);
  try {
    const res = await lsRpc(
      ctx.lsAddress,
      ctx.csrfToken,
      'SendAgentMessage',
      {
        recipient: ctx.session,
        senderId: 'ryugi-artifacts',
        displayTitle: 'Ryugi Artifacts',
        content: message,
      },
      signal,
    );
    return { receipt: res.body.trim(), method: 'SendAgentMessage' };
  } catch (err) {
    // Only fall back to SendUserCascadeMessage when SendAgentMessage is rejected (4xx/unimplemented)
    if (err.statusCode && err.statusCode >= 500) throw err;
    const res = await lsRpc(
      ctx.lsAddress,
      ctx.csrfToken,
      'SendUserCascadeMessage',
      {
        cascadeId: ctx.session,
        items: [{ text: message }],
      },
      signal,
    );
    return { receipt: res.body.trim(), method: 'SendUserCascadeMessage' };
  }
}

function watch(ctx) {
  if (!ctx.lsAddress) return;
  const state = claim(ctx);
  if (!state) return;
  const controller = new AbortController();
  const update = (fields) => {
    if (readJson(ctx.file)?.token === state.token)
      fs.writeFileSync(ctx.file, JSON.stringify({ ...state, ...fields }), { mode: 0o600 });
  };
  let channel;
  const queue = createDeliveryQueue({
    baseMs: 500,
    deliver: (event) => deliverComment(ctx, event, controller.signal),
    delivered: (id) => channel.delivered(id),
    onSuccess: (event, { receipt, method }) =>
      update({ artifact: event.artifact, receipt, method, queuedAt: new Date().toISOString() }),
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
    host: 'antigravity',
    session: ctx.session,
    agent: 'Antigravity',
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

function workerFile(project, session, env = process.env) {
  const data = env.PLUGIN_DATA || path.join(project, '.ryugi/artifacts/.state');
  return path.join(data, 'agy-comment-watch', 'workers', `${session}.json`);
}

function ensureWatch(project, env = process.env) {
  const session = UUID.test(env.ANTIGRAVITY_CONVERSATION_ID || '')
    ? env.ANTIGRAVITY_CONVERSATION_ID
    : null;
  const lsAddress = env.ANTIGRAVITY_LS_ADDRESS || '';
  if (!session || !lsAddress) return false;
  let root;
  try {
    root = projectRoot(project || process.cwd());
  } catch {
    return false;
  }
  const existing = readJson(workerFile(root, session, env));
  if (alive(existing?.pid) && existing?.lsAddress === lsAddress) return false;
  const child = spawn(process.execPath, [__filename, 'watch'], {
    cwd: root,
    env: { ...env, ANTIGRAVITY_CONVERSATION_ID: session },
    detached: true,
    stdio: ['pipe', 'ignore', 'ignore'],
  });
  child.stdin.end(JSON.stringify({ conversationId: session, cwd: root }));
  child.unref();
  return true;
}

function main() {
  setRyugiTitle('watch-comments');
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

module.exports = { context, deliverComment, ensureWatch, lsRpc, projectRoot };
if (require.main === module) main();
