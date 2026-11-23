'use strict';

const MAX_BACKOFF_MS = 30000;

const keyOf = (project, artifact, type) =>
  `${project}\0${artifact}\0${type === 'ryugi-choices' ? 'choices' : type === 'ryugi-answers' ? 'answers' : 'comments'}`;

function createDeliveryQueue({ deliver, delivered, onSuccess, onFailure, baseMs = 1000 }) {
  const pending = new Map();
  let inflight = null;
  let failures = 0;
  let nextAttempt = 0;
  let timer = null;
  let closed = false;

  const later = (ms) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      void run();
    }, ms);
  };

  async function run() {
    if (closed || inflight || !pending.size) return;
    if (Date.now() < nextAttempt) return later(nextAttempt - Date.now());
    const [key, item] = pending.entries().next().value;
    inflight = item;
    try {
      const result = await deliver(item.event);
      if (pending.get(key) === item) pending.delete(key);
      failures = 0;
      for (const id of item.ids) delivered(id);
      onSuccess?.(item.event, result);
    } catch (error) {
      nextAttempt = Date.now() + Math.min(MAX_BACKOFF_MS, baseMs * 2 ** failures++);
      onFailure?.(error);
    } finally {
      inflight = null;
    }
    void run();
  }

  return {
    push(event, id) {
      const key = keyOf(event.project, event.artifact, event.type);
      const previous = pending.get(key);
      const carried = previous && previous !== inflight ? previous.ids : [];
      pending.delete(key);
      pending.set(key, { event, ids: [...carried, id] });
      void run();
    },
    retract({ project, artifact, type }) {
      pending.delete(keyOf(project, artifact, type));
    },
    close() {
      closed = true;
      clearTimeout(timer);
    },
  };
}

module.exports = { createDeliveryQueue };
