'use strict';

const { execFileSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { matchCustomHost } = require('./custom-hosts.cjs');

const UUID = /^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i;
const ARTIFACT = /^(?:document|artboard|whiteboard|slides|storyboard|preview)\/[a-z0-9][a-z0-9-]*$/;
const HOSTS = {
  codex: 'CODEX_THREAD_ID',
  claude: 'CLAUDE_CODE_SESSION_ID',
  pi: 'PI_SESSION_ID',
  antigravity: 'ANTIGRAVITY_CONVERSATION_ID',
};

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function projectRoot(cwd) {
  const dir = fs.realpathSync(cwd);
  const chain = [];
  for (let current = dir; ; current = path.dirname(current)) {
    chain.push(current);
    if (fs.existsSync(path.join(current, '.git')) && (current !== os.homedir() || dir === current))
      return chain.find((item) => fs.existsSync(path.join(item, '.ryugi/artifacts'))) || current;
    if (path.dirname(current) === current) return dir;
  }
}

function gitRoot(dir) {
  for (let current = dir; ; current = path.dirname(current)) {
    if (fs.existsSync(path.join(current, '.git'))) return current;
    if (path.dirname(current) === current) return null;
  }
}

// A linked worktree is its own project root, so a session can subscribe in a checkout its watcher was not started in.
function checkouts(project) {
  const roots = [project];
  try {
    const root = gitRoot(project);
    let common = path.join(root, '.git');
    if (fs.statSync(common).isFile()) {
      const gitdir = path.resolve(
        root,
        fs
          .readFileSync(common, 'utf8')
          .replace(/^gitdir:\s*/, '')
          .trim(),
      );
      common = path.resolve(gitdir, fs.readFileSync(path.join(gitdir, 'commondir'), 'utf8').trim());
      roots.push(path.dirname(common));
    }
    for (const name of fs.readdirSync(path.join(common, 'worktrees'))) {
      const entry = path.join(common, 'worktrees', name);
      try {
        const link = fs.readFileSync(path.join(entry, 'gitdir'), 'utf8').trim();
        roots.push(fs.realpathSync(path.dirname(path.resolve(entry, link))));
      } catch {}
    }
  } catch {}
  return [...new Set(roots)];
}

function sessionOf(host, env = process.env) {
  const session = env[HOSTS[host]] || (host === 'codex' ? env.CODEX_SESSION_ID : null);
  return UUID.test(session || '') ? session : null;
}

function lineage() {
  try {
    let processes;
    if (process.platform === 'win32') {
      const output = execFileSync(
        'powershell.exe',
        [
          '-NoProfile',
          '-NonInteractive',
          '-Command',
          'Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,@{Name="Started";Expression={$_.CreationDate.ToUniversalTime().ToString("o")}} | ConvertTo-Json -Compress',
        ],
        { encoding: 'utf8', timeout: 3000, maxBuffer: 4 * 1024 * 1024 },
      );
      const rows = JSON.parse(output);
      processes = (Array.isArray(rows) ? rows : [rows]).map((p) => ({
        pid: p.ProcessId,
        parent: p.ParentProcessId,
        name: p.Name,
        started: p.Started,
      }));
    } else {
      const output = execFileSync('ps', ['-axo', 'pid=,ppid=,lstart=,comm='], {
        encoding: 'utf8',
        timeout: 1000,
        maxBuffer: 4 * 1024 * 1024,
        env: { ...process.env, LC_ALL: 'C' },
      });
      processes = output.split('\n').flatMap((line) => {
        const m = line.match(
          /^\s*(\d+)\s+(\d+)\s+(\w{3}\s+\w{3}\s+\d+\s+\d+:\d+:\d+\s+\d{4})\s+(\S.*)$/,
        );
        return m
          ? [{ pid: Number(m[1]), parent: Number(m[2]), started: m[3], name: path.basename(m[4]) }]
          : [];
      });
    }
    const byPid = new Map(processes.map((p) => [p.pid, p]));
    const result = [];
    const seen = new Set();
    for (let pid = process.ppid; pid > 1 && !seen.has(pid);) {
      seen.add(pid);
      const p = byPid.get(pid);
      if (!p) break;
      result.push(p);
      pid = p.parent;
    }
    return result;
  } catch {
    return [];
  }
}

const bindingFile = (session, env) =>
  path.join(
    env.XDG_CACHE_HOME || process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache'),
    'ryugi',
    'codex-comment-watch',
    'contexts',
    `${session}.json`,
  );

// Only hook stdin supplies the canonical session. An inherited thread id is a hint, not authority.
function bindCodexSession(session, env = process.env) {
  if (!UUID.test(session || '')) return;
  const ancestors = lineage();
  // Tool and hook runners may insert temporary Node processes. Prefer the
  // persistent Codex host over those wrappers; embedded hosts have no Codex executable.
  const owner =
    ancestors.find((p) => /^codex(?:\.exe)?$/i.test(p.name)) ||
    ancestors.find(
      (p) => !/^(?:ba|z|fi|da)?sh(?:\.exe)?$|^(?:cmd|powershell|pwsh)(?:\.exe)?$/i.test(p.name),
    );
  if (!owner) throw new Error('Cannot identify the process owning this Codex session.');
  const file = bindingFile(session, env);
  const previous = readJson(file);
  // A process-generation marker, not an authentication secret. Concurrent
  // lifecycle hooks must issue the same invocation even on the first bind.
  const generation = createHash('sha256')
    .update(JSON.stringify([session, owner.pid, owner.started]))
    .digest('hex');
  const token =
    previous?.owner?.pid === owner.pid &&
    previous.owner.started === owner.started &&
    UUID.test(previous.token || '')
      ? previous.token
      : [
          generation.slice(0, 8),
          generation.slice(8, 12),
          generation.slice(12, 16),
          generation.slice(16, 20),
          generation.slice(20, 32),
        ].join('-');
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(
    temporary,
    JSON.stringify({
      session,
      token,
      owner: { pid: owner.pid, started: owner.started },
      inherited: Object.fromEntries(Object.keys(HOSTS).map((host) => [host, sessionOf(host, env)])),
      updatedAt: new Date().toISOString(),
    }),
    { mode: 0o600 },
  );
  fs.renameSync(temporary, file);
  return `${session}:${token}`;
}

function unbindCodexSession(session, env = process.env) {
  if (UUID.test(session || '')) fs.rmSync(bindingFile(session, env), { force: true });
}

function boundCodexSession(env, proof) {
  const directory = path.dirname(bindingFile('unused', env));
  let files;
  try {
    files = fs.readdirSync(directory);
  } catch {
    return null;
  }
  const contexts = files
    .filter((f) => UUID.test(f.replace(/\.json$/, '')))
    .map((f) => readJson(path.join(directory, f)))
    .filter(
      (c) =>
        UUID.test(c?.session || '') && Date.now() - Date.parse(c.updatedAt) < 24 * 60 * 60 * 1000,
    );
  for (const owner of lineage()) {
    let candidates = contexts.filter(
      (c) => c.owner?.pid === owner.pid && c.owner.started === owner.started,
    );
    if (!candidates.length) continue;
    if (proof) {
      const [session, token, extra] = proof.split(':');
      const bound = !extra && candidates.find((c) => c.session === session && c.token === token);
      if (!bound)
        throw new Error('Artifact feedback session binding does not belong to this host process.');
      return bound.session;
    }
    candidates = candidates.filter((c) =>
      ['claude', 'pi', 'antigravity'].every(
        (host) => !sessionOf(host, env) || sessionOf(host, env) === c.inherited?.[host],
      ),
    );
    if (!candidates.length) continue;
    if (candidates.length === 1) return candidates[0].session;
    const hints = new Set([
      sessionOf('codex', env),
      UUID.test(env.CODEX_SESSION_ID || '') ? env.CODEX_SESSION_ID : null,
    ]);
    const matching = candidates.filter((c) => hints.has(c.session));
    if (
      matching.length === 1 &&
      !candidates.some((c) => c !== matching[0] && c.inherited?.codex === matching[0].session)
    )
      return matching[0].session;
    throw new Error(
      'Artifact feedback has ambiguous Codex session bindings; refusing to use an inherited parent id.',
    );
  }
  return null;
}

function identity(env, proof) {
  const custom = matchCustomHost(env);
  if (custom) return { host: custom.host, session: custom.session };
  if (proof || sessionOf('codex', env)) {
    const session = boundCodexSession(env, proof);
    if (session) return { host: 'codex', session };
    if (proof) throw new Error('Artifact feedback session binding is no longer active.');
  }
  if (env.ANTIGRAVITY_AGENT && sessionOf('antigravity', env)) {
    return { host: 'antigravity', session: sessionOf('antigravity', env) };
  }
  const hosts = ['claude', 'pi'].filter((host) => sessionOf(host, env));
  if (hosts.length === 1) return { host: hosts[0], session: sessionOf(hosts[0], env) };
  if (hosts.length > 1) throw new Error('Artifact feedback has ambiguous agent session markers.');
  if (sessionOf('codex', env))
    throw new Error('Artifact feedback needs a current Codex hook session binding.');
  if (sessionOf('antigravity', env))
    return { host: 'antigravity', session: sessionOf('antigravity', env) };
  return null;
}

// The launcher knows the real argv and cwd; hook text cannot safely reconstruct shell commands.
function subscriptionFor(args, env = process.env, proof) {
  const isStart = args[0] === 'start';
  const isPreviewRead = args[0] === 'comment' && (args[1] === 'list' || args[1] === 'read');
  if (!isStart && !isPreviewRead) return null;
  const option = (name) => {
    const index = args.indexOf(name);
    return index >= 0
      ? args[index + 1]
      : args.find((arg) => arg.startsWith(`${name}=`))?.slice(name.length + 1);
  };
  const artifact = option('--artifact');
  if (!ARTIFACT.test(artifact || '')) return null;
  if (isPreviewRead && !artifact.startsWith('preview/')) return null;
  const current = identity(env, proof);
  if (!current) return null;
  return { ...current, project: projectRoot(option('--project-dir') || process.cwd()), artifact };
}

module.exports = {
  bindCodexSession,
  checkouts,
  projectRoot,
  sessionOf,
  subscriptionFor,
  unbindCodexSession,
  UUID,
};
