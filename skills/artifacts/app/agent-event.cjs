'use strict';

const { setRyugiTitle } = require('./process-title.cjs');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const PATH_FIELDS = ['file_path', 'path', 'notebook_path', 'Path', 'TargetFile', 'target_file'];
const PATCH_FILE = /^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$/gm;

function postToServer(project, pathname, body) {
  return postToHub(
    path.join(project, '.ryugi', 'artifacts', '.state', 'server-info'),
    project,
    pathname,
    body,
  );
}

function postToHub(infoFile, project, pathname, body) {
  return new Promise((resolve) => {
    let base;
    try {
      const info = JSON.parse(fs.readFileSync(infoFile, 'utf8'));
      base = new URL(info.url);
    } catch {
      resolve();
      return;
    }
    const key = base.searchParams.get('key') || '';
    const payload = body === undefined ? null : JSON.stringify(body);
    const finish = () => {
      clearTimeout(deadline);
      req.destroy();
      resolve();
    };
    const req = http.request(
      {
        host: base.hostname === 'localhost' ? '127.0.0.1' : base.hostname,
        port: base.port,
        method: 'POST',
        path: `${pathname}?key=${encodeURIComponent(key)}`,
        headers: {
          'X-Ryugi-Project': encodeURIComponent(project),
          ...(payload ? { 'Content-Type': 'application/json' } : {}),
        },
      },
      (res) => {
        res.on('error', finish);
        res.on('end', finish);
        res.resume();
      },
    );
    // Socket idle timeouts reset on data. Bound the entire request instead,
    // leaving room for stdin and process startup inside Codex's 3s hooks.
    const deadline = setTimeout(finish, 1500);
    req.on('error', finish);
    req.on('close', finish);
    req.end(payload ?? undefined);
  });
}

function strings(value, out = []) {
  if (typeof value === 'string') out.push(value);
  else if (Array.isArray(value)) for (const item of value) strings(item, out);
  else if (value && typeof value === 'object')
    for (const item of Object.values(value)) strings(item, out);
  return out;
}

function pathsOf(input) {
  const tool =
    input.tool_input && typeof input.tool_input === 'object'
      ? input.tool_input
      : input.toolCall && typeof input.toolCall.args === 'object'
        ? input.toolCall.args
        : null;
  if (!tool) return [];
  const cwd =
    typeof input.cwd === 'string' && input.cwd
      ? input.cwd
      : Array.isArray(input.workspacePaths) && typeof input.workspacePaths[0] === 'string'
        ? input.workspacePaths[0]
        : process.cwd();
  const found = PATH_FIELDS.map((field) => tool[field]).filter(
    (value) => typeof value === 'string',
  );
  for (const text of strings(tool))
    for (const match of text.matchAll(PATCH_FILE)) found.push((match[1] ?? match[2]).trim());
  return [...new Set(found.map((file) => path.resolve(cwd, file)))];
}

function eventFrom(input, host, at = Date.now()) {
  if (!input || typeof input !== 'object') return null;
  const session =
    typeof input.session_id === 'string' && input.session_id
      ? input.session_id
      : typeof input.conversationId === 'string' && input.conversationId
        ? input.conversationId
        : null;
  const rawEvent =
    typeof input.hook_event_name === 'string' && input.hook_event_name
      ? input.hook_event_name
      : typeof input.hookEventName === 'string' && input.hookEventName
        ? input.hookEventName
        : null;
  if (!session || !rawEvent) return null;
  if (
    rawEvent === 'PreInvocation' &&
    typeof input.invocationNum === 'number' &&
    input.invocationNum > 0
  )
    return null;
  const eventName = rawEvent === 'PreInvocation' ? 'UserPromptSubmit' : rawEvent;
  const resolvedHost =
    host === 'antigravity' || (!input.session_id && typeof input.conversationId === 'string')
      ? 'antigravity'
      : host;
  const event = { host: resolvedHost, session, event: eventName, at };
  if (eventName === 'PreToolUse') {
    event.paths = pathsOf(input).slice(0, 64);
    const toolName =
      typeof input.tool_name === 'string'
        ? input.tool_name
        : typeof input.toolCall?.name === 'string'
          ? input.toolCall.name
          : null;
    if (toolName && toolName.length <= 64) event.tool = toolName;
  }
  return event;
}

function readStdin(timeoutMs = 1000) {
  return new Promise((resolve) => {
    if (process.stdin.isTTY) {
      resolve(null);
      return;
    }
    const chunks = [];
    const finish = (value) => {
      clearTimeout(timer);
      process.stdin.removeAllListeners();
      process.stdin.destroy();
      resolve(value);
    };
    const timer = setTimeout(() => finish(null), timeoutMs);
    process.stdin.on('data', (chunk) => chunks.push(chunk));
    process.stdin.on('error', () => finish(null));
    process.stdin.on('end', () => {
      try {
        finish(JSON.parse(Buffer.concat(chunks).toString('utf8')));
      } catch {
        finish(null);
      }
    });
  });
}

function hasHub(project) {
  return fs.existsSync(path.join(project, '.ryugi', 'artifacts', '.state', 'server-info'));
}

// A linked worktree rarely runs its own hub; its sessions belong on the hub of a sibling checkout.
function hubProjectOf(project) {
  if (hasHub(project)) return project;
  try {
    const { checkouts } = require('./comment-subscriptions.cjs');
    return checkouts(project).find(hasHub) || project;
  } catch {
    return project;
  }
}

function projectOf(cwd) {
  try {
    return require('./comment-subscriptions.cjs').projectRoot(cwd);
  } catch {
    return null;
  }
}

if (require.main === module) {
  setRyugiTitle('hook');
  const at = Date.now();
  const host =
    process.argv[2] === 'antigravity'
      ? 'antigravity'
      : process.argv[2] === 'claude'
        ? 'claude'
        : 'codex';
  void readStdin().then((input) => {
    // Antigravity PreToolUse treats {} (missing decision) as deny; empty stdout defers to normal permissions.
    if (host === 'antigravity' && input?.hookEventName !== 'PreToolUse') {
      process.stdout.write('{}\n');
    }
    const event = eventFrom(input, host, at);
    const rawCwd =
      input && typeof input.cwd === 'string' && input.cwd
        ? input.cwd
        : Array.isArray(input?.workspacePaths) && typeof input.workspacePaths[0] === 'string'
          ? input.workspacePaths[0]
          : null;
    const project = (rawCwd ? projectOf(rawCwd) : null) || process.argv[3] || null;
    if (event && project) void postToServer(hubProjectOf(project), '/api/agent/event', event);
  });
}

module.exports = { eventFrom, hubProjectOf, pathsOf, postToHub, postToServer, readStdin };
