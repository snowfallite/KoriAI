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

/** Streams run events; the browser reconnects with Last-Event-ID on its own. `onClosed` fires once
 * when the server ends the stream without run.finished (tech.md §7): it refused a reconnect with
 * 404 after a restart or 410 after the replay buffer expired, so the run is over and the client
 * takes it from REST. */
export function subscribeRun(
	runId: string,
	onEvent: (event: StreamEvent) => void,
	onClosed?: () => void
): () => void {
	const source = new EventSource(`/api/chat/runs/${runId}/events`);
	let done = false;
	const close = () => {
		done = true;
		source.close();
	};
	for (const type of STREAM_EVENT_TYPES) {
		source.addEventListener(type, (message) => {
			const event = JSON.parse(message.data) as StreamEvent;
			onEvent(event);
			// run.finished is the last frame: an open source would reconnect after the server closes.
			if (event.type === 'run.finished') close();
		});
	}
	source.addEventListener('error', () => {
		// A broken connection leaves the source CONNECTING until the next try; a refused one
		// leaves it CLOSED for good.
		if (done || source.readyState !== EventSource.CLOSED) return;
		done = true;
		onClosed?.();
	});
	return close;
}
