import type { StreamEvent } from '$lib/types';

/** Event names of the run stream (tech.md §7); sse.test.ts checks them against the OpenAPI. */
export const STREAM_EVENT_TYPES = [
	'run.queued',
	'run.started',
	'run.routed',
	'step.started',
	'tool.started',
	'tool.finished',
	'artifact.created',
	'source.added',
	'text.delta',
	'text.reset',
	'run.warning',
	'run.finished',
	'dev.echo'
] as const satisfies readonly StreamEvent['type'][];

/** Streams run events; the browser reconnects with Last-Event-ID on its own. */
export function subscribeRun(runId: string, onEvent: (event: StreamEvent) => void): () => void {
	const source = new EventSource(`/api/chat/runs/${runId}/events`);
	const close = () => source.close();
	for (const type of STREAM_EVENT_TYPES) {
		source.addEventListener(type, (message) => {
			const event = JSON.parse(message.data) as StreamEvent;
			onEvent(event);
			// run.finished is the last frame: an open source would reconnect after the server closes.
			if (event.type === 'run.finished') close();
		});
	}
	return close;
}
