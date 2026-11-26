Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
// \0rolldown/runtime.js
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
	if (from && typeof from === "object" || typeof from === "function") for (var keys = __getOwnPropNames(from), i = 0, n = keys.length, key; i < n; i++) {
		key = keys[i];
		if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
			get: ((k) => from[k]).bind(null, key),
			enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
		});
	}
	return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule || !__hasOwnProp.call(mod, "default") ? __defProp(target, "default", {
	value: mod,
	enumerable: true
}) : target, mod));
let node_fs = require("node:fs");
node_fs = __toESM(node_fs, 1);
let node_os = require("node:os");
node_os = __toESM(node_os, 1);
let node_path = require("node:path");
node_path = __toESM(node_path, 1);
// ../shared/src/types.ts
const ARTIFACT_TYPES = [
	"artboard",
	"document",
	"html",
	"whiteboard",
	"verify",
	"slides",
	"report",
	"storyboard"
];
// ../shared/src/validate.ts
const BOARD_NUMBERS = [
	"x",
	"y",
	"w",
	"h"
];
[...BOARD_NUMBERS];
[...BOARD_NUMBERS];
// src/core/server/cloud/credentials.ts
function credentialsFile(env, platform, home) {
	if (platform === "win32" && env.APPDATA) return node_path.default.join(env.APPDATA, "ryugi", "credentials.json");
	return node_path.default.join(env.XDG_CONFIG_HOME || node_path.default.join(home, ".config"), "ryugi", "credentials.json");
}
// src/core/server/cloud/settings.ts
const settingsFileFor = (credentialsFile) => node_path.default.join(node_path.default.dirname(credentialsFile), "config.json");
// src/core/cli/kit/paths.ts
var CliError = class extends Error {
	fields;
	code;
	constructor(message, fields = {}, code = 1) {
		super(message);
		this.fields = fields;
		this.code = code;
	}
};
function projectRoot(dir) {
	let home = "";
	try {
		home = node_fs.default.realpathSync(node_os.default.homedir());
	} catch {}
	const chain = [];
	for (let current = dir;; current = node_path.default.dirname(current)) {
		chain.push(current);
		if (node_fs.default.existsSync(node_path.default.join(current, ".git")) && (current !== home || dir === home)) break;
		if (node_path.default.dirname(current) === current) return dir;
	}
	return chain.find((candidate) => node_fs.default.existsSync(node_path.default.join(candidate, ".ryugi", "artifacts"))) ?? chain.at(-1);
}
function projectPaths(dir) {
	let project;
	try {
		project = node_fs.default.realpathSync(node_path.default.resolve(dir));
		if (!node_fs.default.statSync(project).isDirectory()) throw new Error("Not a directory");
	} catch {
		throw new CliError(`Project directory not found: ${dir}`);
	}
	project = projectRoot(project);
	const root = node_path.default.join(project, ".ryugi", "artifacts");
	const state = node_path.default.join(root, ".state");
	return {
		project,
		root,
		state,
		pid: node_path.default.join(state, "server.pid"),
		log: node_path.default.join(state, "server.log"),
		serverId: node_path.default.join(state, "server-instance-id"),
		info: node_path.default.join(state, "server-info"),
		version: node_path.default.join(state, "server-version"),
		owners: node_path.default.join(state, "owners"),
		stopped: node_path.default.join(state, "server-stopped"),
		lock: node_path.default.join(state, "start.lock")
	};
}
new RegExp(`^(${ARTIFACT_TYPES.join("|")})/[a-z0-9][a-z0-9-]*$`);
`${ARTIFACT_TYPES.slice(0, -1).join(", ")}${ARTIFACT_TYPES.at(-1)}`;
// src/core/cli/output/normalize.ts
var OutputError = class extends Error {
	error;
	kind;
	raw;
	constructor(error, kind = "failed", raw) {
		super(error.message);
		this.error = error;
		this.kind = kind;
		this.raw = raw;
	}
};
function completionState(completion, warning = false) {
	switch (completion.kind) {
		case "succeeded": return {
			outcome: warning ? "attention" : "success",
			code: 0
		};
		case "validation_failed": return {
			outcome: "attention",
			code: 3
		};
		case "pending": return {
			outcome: "pending",
			code: 4
		};
		case "action_required": return {
			outcome: "attention",
			code: 2
		};
		case "partial": return {
			outcome: "partial",
			code: 5
		};
		case "failed": return {
			outcome: "error",
			code: 1
		};
		case "interrupted": return {
			outcome: "error",
			code: completion.signal === "SIGINT" ? 130 : 143
		};
	}
}
function project(value, keys, path, omitted) {
	if (!value || typeof value !== "object" || Array.isArray(value)) return value;
	return Object.fromEntries(Object.entries(value).filter(([key]) => {
		if (keys.includes(key)) return true;
		omitted.push({
			path: `${path}.${key}`,
			reason: "fields"
		});
		return false;
	}));
}
function normalize(command, result, options, policy) {
	const omitted = [...result.coverage.omitted ?? []];
	let data = result.data;
	if (options.fields) {
		const keys = [.../* @__PURE__ */ new Set([...options.fields, ...policy.requiredFields ?? []])];
		if (policy.collection && data && typeof data === "object") {
			const record = data;
			const rows = record[policy.collection];
			data = {
				...record,
				[policy.collection]: Array.isArray(rows) ? rows.map((row, i) => project(row, keys, `data.${policy.collection}.${i}`, omitted)) : rows
			};
		} else data = project(data, keys, "data", omitted);
	}
	return {
		schema: "ryugi.cli/v1",
		command,
		outcome: completionState(result.completion, result.warnings.length > 0).outcome,
		data,
		...result.coverage.page ? { page: result.coverage.page } : {},
		...omitted.length ? { omitted } : {},
		...result.effects.length ? { effects: result.effects } : {},
		...result.warnings.length ? { warnings: result.warnings } : {},
		...result.actions.length ? { next: result.actions } : {},
		...result.completion.kind === "failed" ? { error: result.completion.error } : result.completion.kind === "interrupted" ? { error: {
			code: "E_INTERRUPTED",
			message: `Command interrupted by ${result.completion.signal}.`,
			details: { signal: result.completion.signal }
		} } : {}
	};
}
// src/core/cli/output/planning.ts
function scanOptions(argv, optionSpecs) {
	const values = {};
	for (let i = 0; i < argv.length; i++) {
		const token = argv[i];
		if (token === "--") break;
		if (!token.startsWith("--")) continue;
		const equal = token.indexOf("=");
		const name = token.slice(2, equal < 0 ? void 0 : equal);
		const type = name === "source" ? "boolean" : optionSpecs[name]?.type;
		if (type === "string") values[name] = equal < 0 ? argv[++i] ?? "" : token.slice(equal + 1);
		else if (type === "boolean") values[name] = true;
	}
	return values;
}
function selectOutput(argv, optionSpecs, env = process.env) {
	const values = scanOptions(argv, optionSpecs);
	const explicit = [
		"format",
		"json",
		"quiet",
		"source"
	].filter((key) => values[key] !== void 0);
	const configured = env.RYUGI_ARTIFACTS_FORMAT ?? "brief";
	const requested = values.format ?? (values.json ? "json" : values.quiet ? "quiet" : values.source ? "source" : configured);
	const valid = [
		"brief",
		"table",
		"json",
		"jsonl",
		"raw",
		"source",
		"quiet"
	].includes(requested);
	const options = {
		format: valid ? requested : "brief",
		detail: !!values.detail || !!values.source,
		verbose: !!values.verbose
	};
	let error;
	if (explicit.length > 1) error = new OutputError({
		code: "E_OPTION_CONFLICT",
		message: "Choose one of --format, --json, --quiet or --source."
	});
	else if (!valid || !explicit.length && ![
		"brief",
		"json",
		"jsonl"
	].includes(configured)) error = new OutputError({
		code: "E_FORMAT_UNSUPPORTED",
		message: `Unknown output format: ${String(requested)}`
	});
	if (typeof values.fields === "string") {
		options.fields = values.fields.split(",").map((field) => field.trim());
		if (options.fields.some((field) => !field)) error = new OutputError({
			code: "E_ARGUMENT_INVALID",
			message: "--fields requires comma-separated field names."
		});
	}
	return {
		options,
		...error ? { error } : {}
	};
}
// src/core/cli/output/configuration.ts
const PERSISTED_FORMATS = [
	"brief",
	"json",
	"jsonl"
];
function outputFiles(projectDir) {
	return {
		global: settingsFileFor(credentialsFile(process.env, process.platform, node_os.default.homedir())),
		project: node_path.default.join(node_path.default.dirname(projectPaths(projectDir).root), "config.json")
	};
}
function read(file) {
	try {
		const raw = JSON.parse(node_fs.default.readFileSync(file, "utf8"));
		if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("Expected an object");
		return raw;
	} catch (error) {
		if (error.code === "ENOENT") return {};
		throw new OutputError({
			code: "E_CONFIG_INVALID",
			message: `Cannot read ${file}: ${error.message}`
		});
	}
}
function outputValues(projectDir) {
	const files = outputFiles(projectDir);
	const get = (file) => {
		const output = read(file).output;
		if (output?.format !== void 0 && !PERSISTED_FORMATS.includes(output.format)) throw new OutputError({
			code: "E_FORMAT_UNSUPPORTED",
			message: `Unsupported output format in ${file}: ${String(output.format)}`
		});
		return output && PERSISTED_FORMATS.includes(output.format) ? output.format : null;
	};
	const global = get(files.global), project = get(files.project);
	return {
		global,
		project,
		effective: project ?? global ?? "brief",
		source: project ? "project" : global ? "global" : "default"
	};
}
function configuredEnvironment(argv, specs, env = process.env) {
	if (env.RYUGI_ARTIFACTS_FORMAT !== void 0) return env;
	const values = scanOptions(argv, specs);
	if ([
		"format",
		"json",
		"quiet",
		"source"
	].some((key) => values[key] !== void 0)) return env;
	let project = typeof values["project-dir"] === "string" ? values["project-dir"] : process.cwd();
	if (!values["project-dir"] && argv[0] && !argv[0].startsWith("-")) try {
		if (node_fs.default.statSync(argv[0]).isDirectory()) project = argv[0];
	} catch {}
	const config = outputValues(project);
	return {
		...env,
		RYUGI_ARTIFACTS_FORMAT: config.effective
	};
}
// src/core/cli/output/protocol.ts
function result(data, completion = { kind: "succeeded" }, extra = {}) {
	return {
		data,
		completion,
		coverage: {},
		effects: [],
		warnings: [],
		actions: [],
		...extra
	};
}
// src/core/cli/output/time.ts
const ISO = /^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)$/;
const two = (n) => String(n).padStart(2, "0");
const isIsoTime = (value) => typeof value === "string" && ISO.test(value) && !Number.isNaN(Date.parse(value));
function formatTime(iso, now = /* @__PURE__ */ new Date()) {
	const at = new Date(iso);
	if (Number.isNaN(at.getTime())) return iso;
	const clock = `${two(at.getHours())}:${two(at.getMinutes())}`;
	if (at.getFullYear() !== now.getFullYear()) return `${at.getFullYear()}-${two(at.getMonth() + 1)}-${two(at.getDate())}`;
	if (at.getMonth() === now.getMonth() && at.getDate() === now.getDate()) return clock;
	return `${two(at.getMonth() + 1)}-${two(at.getDate())} ${clock}`;
}
// src/core/cli/output/view.ts
function recoveryActions(error, subject) {
	const details = error.details;
	if (!details || typeof details !== "object" || Array.isArray(details)) return [];
	return Object.entries(details).flatMap(([key, url]) => typeof url === "string" && /^https?:\/\/\S+$/i.test(url) ? [{
		kind: "url",
		label: subject ? `${subject} ${key}` : key,
		url
	}] : []);
}
// src/core/cli/output/render.ts
const clean = (text) => text.replaceAll(/\p{Cc}/gu, " ");
function flatten(value, nested = false) {
	if (value === null || value === void 0) return "";
	if (Array.isArray(value)) return value.map((item) => flatten(item, true)).join(", ");
	if (typeof value === "object") {
		const text = Object.entries(value).filter(([, item]) => !absent(item)).map(([key, item]) => `${key} ${flatten(item, true)}`).join(nested ? ", " : " · ");
		return nested ? `(${text})` : text;
	}
	return isIsoTime(value) ? formatTime(value) : String(value);
}
const scalar = (value, path, loose) => {
	if (value !== null && typeof value === "object") {
		if (!loose) throw new Error(`Brief cannot print the object at ${path}; flatten it in the view.`);
		return flatten(value);
	}
	return flatten(value);
};
const absent = (value, fallback) => value === void 0 || value === null || value === "" || value === false || fallback !== void 0 && value === fallback;
const EXIT_WORDS = {
	1: "FAILED",
	2: "NEEDS YOU",
	3: "ISSUES",
	4: "INCOMPLETE",
	5: "PARTIAL",
	130: "INTERRUPTED",
	143: "INTERRUPTED"
};
const RECOVERY = {
	E_ARTIFACT_NOT_FOUND: "check --artifact and --project-dir; artifacts live in <project>/.ryugi/artifacts/<type>/<id>/",
	E_ARGUMENT_INVALID: "run the command with --help for its options",
	E_CURSOR_EXPIRED: "run the read again without --cursor or --snapshot",
	E_CURSOR_MISMATCH: "run the read again without --cursor or --snapshot"
};
const statusWord = (status, code) => code ? EXIT_WORDS[code] ?? "FAILED" : clean(status).replaceAll("_", " ").toUpperCase();
const commandName = (id) => {
	const words = id.replaceAll(/[._]/g, " ").trim();
	return words ? words[0].toUpperCase() + words.slice(1) : "Command";
};
function pageText(page) {
	const offset = page.offset ?? 0;
	if (!page.hasMore && offset === 0) return null;
	const of = page.total === null ? "" : ` of ${page.total}`;
	if (page.offset === void 0) return `${page.returned}${of} shown${page.total === null && page.hasMore ? " · more available" : ""}`;
	return `${page.returned ? `${offset + 1}–${offset + page.returned}` : "none"}${of}`;
}
const quote = (value) => /^[\w./:@=+-]+$/.test(value) ? value : `'${value.replaceAll("'", "'\\''")}'`;
function actionText(action) {
	return action.kind === "command" ? action.argv.map(quote).join(" ") : action.url;
}
const effectLines = (effects) => effects.map((effect) => `Effect: ${clean(effect.operation)} ${clean(effect.target)} · ${effect.state}`);
const lastSegment = (path) => path.split(".").filter(Boolean).at(-1) ?? path;
function renderText(view, wire, options, collection, requiredFields = [], code = 0) {
	const head = [
		statusWord(view.status, code),
		view.subject && clean(view.subject),
		view.summary && clean(view.summary)
	].filter(Boolean);
	const lines = [head.length ? `${clean(view.heading)}: ${head.join(" · ")}` : clean(view.heading)];
	const omissions = [...wire.omitted ?? []];
	const selected = (key, required = false) => required || requiredFields.includes(key) || !options.fields || options.fields.includes(key);
	const value = (input, path, loose = false) => clean(scalar(input, path, loose));
	const cell = (label, key, input, path, positional, fallback, loose = false) => {
		if (absent(input, fallback)) return null;
		const name = clean(label ?? key);
		if (input === true) return name;
		const text = value(input, path, loose);
		return positional ? text : `${name} ${text}`;
	};
	const facts = (items, loose = false) => {
		for (const item of items) {
			if (!collection && !selected(item.binding.key, item.required)) continue;
			if (absent(item.binding.value)) continue;
			const text = item.binding.value === true ? "yes" : value(item.binding.value, `data.${item.binding.key}`, loose);
			lines.push(`${clean(item.label)}: ${text}`);
		}
	};
	const metadata = (items, path) => items.map((item) => cell(item.label, item.binding.key, item.binding.value, `${path}.${item.binding.key}`, item.positional)).filter((text) => text !== null).join(" · ");
	const title = (text, summary) => {
		if (text) lines.push(summary ? `${clean(text)} · ${clean(summary)}` : clean(text));
	};
	const pageLine = (page) => {
		const text = page && pageText(page);
		if (text) lines.push(text);
	};
	facts(view.facts);
	const errorActions = wire.error ? recoveryActions(wire.error) : [];
	if (wire.error) {
		lines.push(`${clean(wire.error.code)}: ${clean(wire.error.message)}`);
		if (wire.error.httpStatus !== void 0 && wire.error.httpStatus >= 500) lines.push(`HTTP: ${wire.error.httpStatus}`);
		const hint = RECOVERY[wire.error.code];
		if (hint) lines.push(`Next: ${hint}`);
		const details = wire.error.details;
		if (details && typeof details === "object" && !Array.isArray(details)) {
			for (const [key, detail] of Object.entries(details)) if (!errorActions.some((action) => action.label === key)) facts([{
				label: key,
				binding: {
					key,
					value: detail
				},
				required: true
			}], true);
		} else if (details !== void 0) facts([{
			label: "Details",
			binding: {
				key: "details",
				value: details
			},
			required: true
		}], true);
	}
	if (!collection && options.fields && wire.data && typeof wire.data === "object") {
		const bound = /* @__PURE__ */ new Set([...view.facts.map((item) => item.binding.key), ...view.sections.flatMap((section) => section.kind === "fields" ? section.facts.map((item) => item.binding.key) : [section.key])]);
		const data = wire.data;
		facts([.../* @__PURE__ */ new Set([...options.fields, ...requiredFields])].filter((key) => !bound.has(key) && Object.hasOwn(data, key)).map((key) => ({
			label: key,
			binding: {
				key,
				value: data[key]
			}
		})), true);
	}
	for (const section of view.sections) {
		if (section.kind === "fields") {
			facts(section.facts);
			continue;
		}
		if (!collection && !selected(section.key)) continue;
		const named = "title" in section && section.title ? section.title : void 0;
		if (section.kind === "records") {
			title(named ?? (section.page ? section.key : void 0), section.summary);
			const declared = new Set(section.columns.map((column) => column.key));
			const extra = section.key === collection ? [.../* @__PURE__ */ new Set([...options.fields ?? [], ...options.fields ? requiredFields : []])].filter((key) => !declared.has(key)).map((key) => ({
				key,
				label: key
			})) : [];
			const loose = new Set(extra.map((column) => column.key));
			const columns = [...section.columns, ...extra].filter((column) => section.key !== collection || selected(column.key, column.required));
			if (options.format === "table") {
				const labels = columns.map((column) => column.label ?? column.key);
				const rows = section.rows.map((row, i) => columns.map((column) => absent(row[column.key], column.default) ? "" : value(row[column.key], `data.${section.key}.${i}.${column.key}`, loose.has(column.key))));
				const widths = labels.map((label, i) => Math.max(label.length, ...rows.map((row) => row[i]?.length ?? 0)));
				lines.push(...[labels, ...rows].map((row) => row.map((text, i) => text.padEnd(widths[i] ?? text.length)).join("  ").trimEnd()));
			} else for (const [i, row] of section.rows.entries()) lines.push(`  ${columns.map((column) => cell(column.label, column.key, row[column.key], `data.${section.key}.${i}.${column.key}`, column.positional, column.default, loose.has(column.key))).filter((text) => text !== null).join(" · ")}`);
			if (!section.rows.length && !named && !section.page) lines.push("No records.");
			pageLine(section.page);
		} else if (section.kind === "messages") {
			title(named, section.summary);
			for (const [g, group] of section.groups.entries()) {
				lines.push(`  ${metadata(group.facts, `data.${section.key}.${g}`)}`);
				for (const [m, message] of group.messages.entries()) {
					lines.push(`    ${metadata(message.facts, `data.${section.key}.${g}.messages.${m}`)}`);
					lines.push(...message.text.split("\n").map((line) => `      ${line.replaceAll(/\p{Cc}/gu, (char) => char === "	" ? char : "")}`));
				}
			}
			if (!section.groups.length && !named && !section.page) lines.push("No messages.");
			pageLine(section.page);
		} else if (section.kind === "diagnostics") {
			const limit = options.detail ? section.items.length : section.preview ?? 3;
			for (const item of section.items.slice(0, limit)) lines.push(`  ${item.location ? `${clean(item.location)}  ` : ""}${clean(item.code)}: ${value(item.message, `data.${section.key}`)}`);
			if (limit < section.items.length) omissions.push({
				path: `data.${section.key}`,
				reason: "preview",
				count: section.items.length - limit
			});
		} else {
			title(named && `${named}:`, section.summary);
			lines.push(...section.text.trimEnd().split("\n").map((line) => `  ${line.replaceAll(/\p{Cc}/gu, (char) => char === "	" || char === "\n" ? char : "")}`));
		}
	}
	if (wire.page) pageLine(wire.page);
	if (code || (wire.effects ?? []).some((effect) => effect.state !== "confirmed")) lines.push(...effectLines(wire.effects ?? []));
	for (const warning of wire.warnings ?? []) lines.push(`Warning: ${clean(warning.message)}`);
	const given = view.actions ?? wire.next ?? [];
	const actions = [...given, ...errorActions.filter((action) => !given.some((other) => actionText(other) === actionText(action)))];
	const used = /* @__PURE__ */ new Set();
	const details = actions.find((action) => action.label === "Details");
	for (const omission of omissions) {
		if (omission.count === void 0) continue;
		const more = `${omission.count} more ${lastSegment(omission.path)}`;
		if (details && !used.has(details)) {
			used.add(details);
			lines.push(`${more} · Details: ${actionText(details)}`);
		} else lines.push(more);
	}
	for (const action of actions) if (!used.has(action)) lines.push(`${clean(action.label ?? "Next")}: ${action.reason ? `${clean(action.reason)} · ` : ""}${actionText(action)}`);
	return `${lines.join("\n")}\n`;
}
function renderFailure(wire, options, code = 1) {
	return renderText({
		heading: commandName(wire.command),
		status: "",
		facts: [],
		sections: []
	}, wire, {
		...options,
		fields: void 0
	}, void 0, [], code);
}
// src/core/cli/output/bootstrap/index.ts
function resolveSelection(argv) {
	return selectOutput(argv, {
		"format": { "type": "string" },
		"json": { "type": "boolean" },
		"detail": { "type": "boolean" },
		"fields": { "type": "string" },
		"quiet": { "type": "boolean" },
		"verbose": { "type": "boolean" },
		"project-dir": { "type": "string" },
		"artifact": { "type": "string" },
		"host": { "type": "string" },
		"url-host": { "type": "string" },
		"port": { "type": "string" },
		"open": { "type": "boolean" },
		"no-open": { "type": "boolean" },
		"foreground": { "type": "boolean" },
		"background": { "type": "boolean" },
		"mockup": { "type": "boolean" },
		"base": { "type": "string" },
		"input": { "type": "string" },
		"page": { "type": "string" },
		"visibility": { "type": "string" },
		"type": { "type": "string" },
		"project": { "type": "boolean" },
		"module": { "type": "string" },
		"limit": { "type": "string" },
		"cursor": { "type": "string" },
		"public": { "type": "boolean" },
		"private": { "type": "boolean" },
		"key": { "type": "boolean" },
		"expires": { "type": "string" },
		"new-key": { "type": "boolean" },
		"revoke-key": { "type": "boolean" },
		"profile": { "type": "boolean" },
		"no-profile": { "type": "boolean" },
		"unpublish": { "type": "boolean" },
		"list": { "type": "boolean" },
		"delete": { "type": "string" },
		"space": { "type": "string" },
		"move-to": { "type": "string" },
		"no-refs": { "type": "boolean" },
		"login": { "type": "boolean" },
		"with-token": { "type": "boolean" },
		"from": { "type": "string" },
		"logout": { "type": "boolean" },
		"as": { "type": "string" },
		"dry-run": { "type": "boolean" },
		"force": { "type": "boolean" },
		"only": { "type": "string" },
		"line": { "type": "string" },
		"wait": { "type": "boolean" },
		"file": { "type": "string" },
		"map": { "type": "string" },
		"master": { "type": "string" },
		"id": { "type": "string" },
		"url": { "type": "string" },
		"all": { "type": "boolean" },
		"thread": { "type": "string" },
		"text": { "type": "string" },
		"receipt": { "type": "string" },
		"agent": { "type": "string" },
		"set": { "type": "string" },
		"sections": { "type": "string" },
		"section": { "type": "string" },
		"snapshot": { "type": "string" },
		"status": { "type": "string" },
		"waiting-on": { "type": "string" },
		"kind": { "type": "string" },
		"claim": { "type": "string" },
		"gap": { "type": "string" },
		"choice-state": { "type": "string" },
		"block": { "type": "string" },
		"quote": { "type": "string" },
		"node": { "type": "string" },
		"edge": { "type": "string" },
		"board": { "type": "string" },
		"element": { "type": "string" },
		"slide": { "type": "string" },
		"shot": { "type": "string" },
		"at": { "type": "string" },
		"cut": { "type": "string" },
		"point": { "type": "string" },
		"row": { "type": "string" },
		"x": { "type": "string" },
		"y": { "type": "string" },
		"group": { "type": "string" },
		"clear": { "type": "boolean" },
		"ask": { "type": "string" },
		"choice": { "type": "string" },
		"round": { "type": "string" },
		"withdraw": { "type": "boolean" },
		"save": { "type": "string" },
		"frame": { "type": "string" },
		"source": { "type": "boolean" },
		"download": { "type": "boolean" },
		"out": { "type": "string" },
		"no-comments": { "type": "boolean" },
		"output-format": { "type": "string" },
		"auto-publish": { "type": "string" },
		"check": { "type": "boolean" },
		"cli-only": { "type": "boolean" },
		"plugins-only": { "type": "boolean" },
		"install-dir": { "type": "string" },
		"plugin-source": { "type": "string" },
		"pm": { "type": "string" },
		"mode": { "type": "string" },
		"harness": { "type": "string" },
		"yes": { "type": "boolean" },
		"no-cli": { "type": "boolean" },
		"bin-dir": { "type": "string" },
		"binary": { "type": "string" },
		"label": { "type": "string" },
		"plugin": { "type": "string" }
	}, configuredEnvironment(argv, {
		"format": { "type": "string" },
		"json": { "type": "boolean" },
		"detail": { "type": "boolean" },
		"fields": { "type": "string" },
		"quiet": { "type": "boolean" },
		"verbose": { "type": "boolean" },
		"project-dir": { "type": "string" },
		"artifact": { "type": "string" },
		"host": { "type": "string" },
		"url-host": { "type": "string" },
		"port": { "type": "string" },
		"open": { "type": "boolean" },
		"no-open": { "type": "boolean" },
		"foreground": { "type": "boolean" },
		"background": { "type": "boolean" },
		"mockup": { "type": "boolean" },
		"base": { "type": "string" },
		"input": { "type": "string" },
		"page": { "type": "string" },
		"visibility": { "type": "string" },
		"type": { "type": "string" },
		"project": { "type": "boolean" },
		"module": { "type": "string" },
		"limit": { "type": "string" },
		"cursor": { "type": "string" },
		"public": { "type": "boolean" },
		"private": { "type": "boolean" },
		"key": { "type": "boolean" },
		"expires": { "type": "string" },
		"new-key": { "type": "boolean" },
		"revoke-key": { "type": "boolean" },
		"profile": { "type": "boolean" },
		"no-profile": { "type": "boolean" },
		"unpublish": { "type": "boolean" },
		"list": { "type": "boolean" },
		"delete": { "type": "string" },
		"space": { "type": "string" },
		"move-to": { "type": "string" },
		"no-refs": { "type": "boolean" },
		"login": { "type": "boolean" },
		"with-token": { "type": "boolean" },
		"from": { "type": "string" },
		"logout": { "type": "boolean" },
		"as": { "type": "string" },
		"dry-run": { "type": "boolean" },
		"force": { "type": "boolean" },
		"only": { "type": "string" },
		"line": { "type": "string" },
		"wait": { "type": "boolean" },
		"file": { "type": "string" },
		"map": { "type": "string" },
		"master": { "type": "string" },
		"id": { "type": "string" },
		"url": { "type": "string" },
		"all": { "type": "boolean" },
		"thread": { "type": "string" },
		"text": { "type": "string" },
		"receipt": { "type": "string" },
		"agent": { "type": "string" },
		"set": { "type": "string" },
		"sections": { "type": "string" },
		"section": { "type": "string" },
		"snapshot": { "type": "string" },
		"status": { "type": "string" },
		"waiting-on": { "type": "string" },
		"kind": { "type": "string" },
		"claim": { "type": "string" },
		"gap": { "type": "string" },
		"choice-state": { "type": "string" },
		"block": { "type": "string" },
		"quote": { "type": "string" },
		"node": { "type": "string" },
		"edge": { "type": "string" },
		"board": { "type": "string" },
		"element": { "type": "string" },
		"slide": { "type": "string" },
		"shot": { "type": "string" },
		"at": { "type": "string" },
		"cut": { "type": "string" },
		"point": { "type": "string" },
		"row": { "type": "string" },
		"x": { "type": "string" },
		"y": { "type": "string" },
		"group": { "type": "string" },
		"clear": { "type": "boolean" },
		"ask": { "type": "string" },
		"choice": { "type": "string" },
		"round": { "type": "string" },
		"withdraw": { "type": "boolean" },
		"save": { "type": "string" },
		"frame": { "type": "string" },
		"source": { "type": "boolean" },
		"download": { "type": "boolean" },
		"out": { "type": "string" },
		"no-comments": { "type": "boolean" },
		"output-format": { "type": "string" },
		"auto-publish": { "type": "string" },
		"check": { "type": "boolean" },
		"cli-only": { "type": "boolean" },
		"plugins-only": { "type": "boolean" },
		"install-dir": { "type": "string" },
		"plugin-source": { "type": "string" },
		"pm": { "type": "string" },
		"mode": { "type": "string" },
		"harness": { "type": "string" },
		"yes": { "type": "boolean" },
		"no-cli": { "type": "boolean" },
		"bin-dir": { "type": "string" },
		"binary": { "type": "string" },
		"label": { "type": "string" },
		"plugin": { "type": "string" }
	}));
}
function reportFailure(argv, error, selection) {
	let selected;
	try {
		selected = selection ?? resolveSelection(argv);
	} catch {
		selected = selectOutput(argv, {
			"format": { "type": "string" },
			"json": { "type": "boolean" },
			"detail": { "type": "boolean" },
			"fields": { "type": "string" },
			"quiet": { "type": "boolean" },
			"verbose": { "type": "boolean" },
			"project-dir": { "type": "string" },
			"artifact": { "type": "string" },
			"host": { "type": "string" },
			"url-host": { "type": "string" },
			"port": { "type": "string" },
			"open": { "type": "boolean" },
			"no-open": { "type": "boolean" },
			"foreground": { "type": "boolean" },
			"background": { "type": "boolean" },
			"mockup": { "type": "boolean" },
			"base": { "type": "string" },
			"input": { "type": "string" },
			"page": { "type": "string" },
			"visibility": { "type": "string" },
			"type": { "type": "string" },
			"project": { "type": "boolean" },
			"module": { "type": "string" },
			"limit": { "type": "string" },
			"cursor": { "type": "string" },
			"public": { "type": "boolean" },
			"private": { "type": "boolean" },
			"key": { "type": "boolean" },
			"expires": { "type": "string" },
			"new-key": { "type": "boolean" },
			"revoke-key": { "type": "boolean" },
			"profile": { "type": "boolean" },
			"no-profile": { "type": "boolean" },
			"unpublish": { "type": "boolean" },
			"list": { "type": "boolean" },
			"delete": { "type": "string" },
			"space": { "type": "string" },
			"move-to": { "type": "string" },
			"no-refs": { "type": "boolean" },
			"login": { "type": "boolean" },
			"with-token": { "type": "boolean" },
			"from": { "type": "string" },
			"logout": { "type": "boolean" },
			"as": { "type": "string" },
			"dry-run": { "type": "boolean" },
			"force": { "type": "boolean" },
			"only": { "type": "string" },
			"line": { "type": "string" },
			"wait": { "type": "boolean" },
			"file": { "type": "string" },
			"map": { "type": "string" },
			"master": { "type": "string" },
			"id": { "type": "string" },
			"url": { "type": "string" },
			"all": { "type": "boolean" },
			"thread": { "type": "string" },
			"text": { "type": "string" },
			"receipt": { "type": "string" },
			"agent": { "type": "string" },
			"set": { "type": "string" },
			"sections": { "type": "string" },
			"section": { "type": "string" },
			"snapshot": { "type": "string" },
			"status": { "type": "string" },
			"waiting-on": { "type": "string" },
			"kind": { "type": "string" },
			"claim": { "type": "string" },
			"gap": { "type": "string" },
			"choice-state": { "type": "string" },
			"block": { "type": "string" },
			"quote": { "type": "string" },
			"node": { "type": "string" },
			"edge": { "type": "string" },
			"board": { "type": "string" },
			"element": { "type": "string" },
			"slide": { "type": "string" },
			"shot": { "type": "string" },
			"at": { "type": "string" },
			"cut": { "type": "string" },
			"point": { "type": "string" },
			"row": { "type": "string" },
			"x": { "type": "string" },
			"y": { "type": "string" },
			"group": { "type": "string" },
			"clear": { "type": "boolean" },
			"ask": { "type": "string" },
			"choice": { "type": "string" },
			"round": { "type": "string" },
			"withdraw": { "type": "boolean" },
			"save": { "type": "string" },
			"frame": { "type": "string" },
			"source": { "type": "boolean" },
			"download": { "type": "boolean" },
			"out": { "type": "string" },
			"no-comments": { "type": "boolean" },
			"output-format": { "type": "string" },
			"auto-publish": { "type": "string" },
			"check": { "type": "boolean" },
			"cli-only": { "type": "boolean" },
			"plugins-only": { "type": "boolean" },
			"install-dir": { "type": "string" },
			"plugin-source": { "type": "string" },
			"pm": { "type": "string" },
			"mode": { "type": "string" },
			"harness": { "type": "string" },
			"yes": { "type": "boolean" },
			"no-cli": { "type": "boolean" },
			"bin-dir": { "type": "string" },
			"binary": { "type": "string" },
			"label": { "type": "string" },
			"plugin": { "type": "string" }
		});
	}
	const message = error instanceof Error ? error.message : String(error);
	const detail = selected.error?.error ?? (error instanceof OutputError ? error.error : {
		code: "E_BOOTSTRAP_FAILED",
		message
	});
	const failure = result(null, {
		kind: "failed",
		error: detail
	});
	const wire = {
		...normalize(argv[0] && !argv[0].startsWith("-") ? argv[0] : "browse", failure, { format: selected.options.format }, { formats: [selected.options.format] }),
		error: detail
	};
	if (selected.options.format === "json") process.stdout.write(`${JSON.stringify(wire)}\n`);
	else if (selected.options.format === "jsonl") process.stdout.write(`${JSON.stringify({
		...wire,
		seq: 0,
		kind: "result"
	})}\n`);
	else process.stderr.write(renderFailure(wire, selected.options));
	process.exitCode = 1;
}
exports.reportFailure = reportFailure;
exports.resolveSelection = resolveSelection;
