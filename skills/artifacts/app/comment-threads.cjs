// Generated from ryugi-cloud/packages/shared/src/review-evidence.ts. Do not edit.
Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
let node_crypto = require("node:crypto");
// ../shared/src/review-evidence.ts
const hash = (value) => (0, node_crypto.createHash)("sha256").update(JSON.stringify(value)).digest("hex");
const reviewStateKey = (artifact, agent) => hash([artifact, agent]);
function humanTokens(thread) {
	const values = thread.messages.filter((message) => message.author === "human").map((message) => ({
		token: hash([
			thread.id,
			"message",
			message.id,
			message.at,
			message.editedAt,
			message.deleted,
			message.text
		]),
		at: message.editedAt ?? message.at
	}));
	if (thread.statusBy === "human") values.push({
		token: hash([
			thread.id,
			"status",
			thread.statusAt,
			thread.status
		]),
		at: thread.statusAt
	});
	return values;
}
function unreadThreadCount(file, consumed = []) {
	const seen = new Set(consumed);
	return (file?.threads ?? []).filter((thread) => {
		const anchor = thread.anchor;
		return anchor.ask === void 0 && anchor.choice === void 0 && anchor.submit === void 0 && humanTokens(thread).some((event) => !seen.has(event.token));
	}).length;
}
exports.humanTokens = humanTokens;
exports.reviewStateKey = reviewStateKey;
exports.unreadThreadCount = unreadThreadCount;
