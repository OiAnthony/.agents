'use strict';

const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { UUID } = require('./comment-subscriptions.cjs');

const MAX_FRAME_BYTES = 8 * 1024 * 1024;

function hasDesktopPipe(env = process.env) {
  return (
    typeof env.CODEX_APP_TOOLS_PIPE_PATH === 'string' &&
    Boolean(env.CODEX_APP_TOOLS_PIPE_PATH.trim())
  );
}

function ensureDesktopRuntime() {
  if (process.platform !== 'darwin' || !hasDesktopPipe()) return;
  const runtime = process.env.CODEX_MCP_NODE_PATH;
  if (!runtime || !path.isAbsolute(runtime))
    throw new Error(
      'Codex desktop must provide an absolute CODEX_MCP_NODE_PATH. Restart this chat in Codex desktop.',
    );
  try {
    fs.accessSync(runtime, fs.constants.X_OK);
    if (!fs.statSync(runtime).isFile()) throw new Error('Not a file');
  } catch {
    throw new Error(
      'The inherited CODEX_MCP_NODE_PATH is not an executable file. Restart this chat in Codex desktop.',
    );
  }
  if (fs.realpathSync(runtime) === fs.realpathSync(process.execPath)) return;
  if (typeof process.execve !== 'function')
    throw new Error(
      'Ryugi desktop watch on macOS requires Node.js 22.15 or newer with process.execve. Update the Node used by the hook, then restart this chat.',
    );
  // Desktop peer authorization checks ancestors. Replace the entire watcher before reading stdin.
  process.execve(runtime, [runtime, ...process.argv.slice(1)], process.env);
}

function encode(value) {
  const payload = Buffer.from(JSON.stringify(value));
  if (payload.length > MAX_FRAME_BYTES)
    throw new Error('Codex desktop callback request was too large.');
  const header = Buffer.alloc(4);
  header.writeUInt32LE(payload.length);
  return Buffer.concat([header, payload]);
}

function acknowledged(result, session) {
  const texts = Array.isArray(result?.contentItems)
    ? result.contentItems
        .filter((item) => item?.type === 'inputText' && typeof item.text === 'string')
        .map((item) => item.text)
    : [];
  if (result?.success !== true)
    throw new Error(texts.join('\n').slice(0, 800) || 'Codex desktop rejected the callback.');
  let receipt;
  try {
    if (texts.length !== 1) throw new Error('Missing receipt');
    receipt = JSON.parse(texts[0]);
  } catch {
    throw new Error('Codex desktop returned an invalid callback receipt.');
  }
  if (receipt?.threadId !== session)
    throw new Error('Codex desktop callback receipt does not match the hook session.');
  return { receipt: texts[0], warning: '' };
}

// Private desktop IPC, intentionally restricted to notifying the originating local chat.
async function sendDesktop(ctx, message, signal, { timeoutMs = 15000 } = {}) {
  const session = ctx?.session;
  if (!UUID.test(session || ''))
    throw new Error('Desktop callback requires the valid hook session ID.');
  if (typeof message !== 'string' || !message.trim())
    throw new Error('Desktop callback requires a message.');
  if (!hasDesktopPipe())
    throw new Error(
      'Codex did not provide CODEX_APP_TOOLS_PIPE_PATH. Restart this chat in Codex desktop.',
    );
  const host = process.env.CODEX_APP_TOOLS_CALLER_HOST_ID?.trim();
  if (host && host !== 'local')
    throw new Error(
      'Ryugi desktop callbacks support the local host only; remote and cloud chats are unsupported.',
    );
  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0)
    throw new Error('Desktop callback timeout must be a positive integer.');
  signal?.throwIfAborted();
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(process.env.CODEX_APP_TOOLS_PIPE_PATH.trim());
    let done = false;
    let id = 1;
    let pending = Buffer.alloc(0);
    const finish = (error, result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
      socket.destroy();
      if (error) reject(error);
      else resolve(result);
    };
    const onAbort = () =>
      finish(
        signal.reason instanceof Error
          ? signal.reason
          : new Error('Codex desktop callback cancelled.'),
      );
    const timer = setTimeout(
      () => finish(new Error('Codex desktop callback timed out. Delivery is unconfirmed.')),
      timeoutMs,
    );
    signal?.addEventListener('abort', onAbort, { once: true });
    const request = (method, params) =>
      socket.write(encode({ jsonrpc: '2.0', id, method, params }));
    const closed = () =>
      finish(
        new Error(
          'Codex desktop pipe closed before acknowledging the callback. Check the inherited CODEX_MCP_NODE_PATH runtime.',
        ),
      );
    socket.on('error', (error) => finish(new Error(`Codex desktop pipe failed: ${error.message}`)));
    socket.on('close', closed);
    socket.on('end', closed);
    socket.once('connect', () => request('tools/list', { threadStartKind: 'all' }));
    socket.on('data', (chunk) => {
      pending = Buffer.concat([pending, chunk]);
      while (!done && pending.length >= 4) {
        const length = pending.readUInt32LE(0);
        if (length > MAX_FRAME_BYTES)
          return finish(new Error('Codex desktop response was too large.'));
        if (pending.length < length + 4) return;
        const payload = pending.subarray(4, length + 4);
        pending = pending.subarray(length + 4);
        let response;
        try {
          response = JSON.parse(payload.toString('utf8'));
          if (
            !response ||
            response.jsonrpc !== '2.0' ||
            (!Object.hasOwn(response, 'result') && !response.error)
          )
            throw new Error('Invalid response');
        } catch {
          return finish(new Error('Codex desktop returned an invalid native response.'));
        }
        if (response.id !== id) continue;
        if (response.error)
          return finish(
            new Error(`Codex desktop RPC error: ${response.error.message || 'Unknown error'}`),
          );
        try {
          if (id === 1) {
            const tool = response.result?.tools?.find(
              (item) => item?.name === 'send_message_to_thread',
            );
            if (!tool || typeof tool.namespace !== 'string' || !tool.namespace.trim())
              throw new Error(
                'send_message_to_thread is not available in the Codex desktop tool catalog.',
              );
            id = 2;
            const callId = randomUUID();
            request('tools/call', {
              callerSource: 'codex',
              hostId: 'local',
              namespace: tool.namespace,
              tool: 'send_message_to_thread',
              threadId: session,
              turnId: `mcp-turn-${callId}`,
              callId,
              arguments: { threadId: session, hostId: 'local', prompt: message },
            });
          } else {
            finish(null, acknowledged(response.result, session));
          }
        } catch (error) {
          finish(error);
        }
      }
    });
  });
}

module.exports = { ensureDesktopRuntime, hasDesktopPipe, sendDesktop };
