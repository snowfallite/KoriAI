import { beforeEach, describe, expect, it, vi } from 'vitest';
import openapi from './openapi.json';
import { STREAM_EVENT_TYPES, subscribeRun } from './sse';

type Listener = (message: MessageEvent<string>) => void;

class FakeEventSource {
	static last: FakeEventSource | undefined;
	readonly listeners = new Map<string, Listener>();
	closed = false;

	constructor(readonly url: string) {
		FakeEventSource.last = this;
	}

	addEventListener(type: string, listener: Listener) {
		this.listeners.set(type, listener);
	}

	close() {
		this.closed = true;
	}

	emit(data: { type: string; [field: string]: unknown }) {
		this.listeners.get(data.type)?.(new MessageEvent(data.type, { data: JSON.stringify(data) }));
	}
}

function source(): FakeEventSource {
	if (!FakeEventSource.last) throw new Error('no EventSource opened');
	return FakeEventSource.last;
}

const base = { seq: 1, run_id: 'r1', ts: '2026-09-29T00:00:00Z' };

beforeEach(() => {
	FakeEventSource.last = undefined;
	vi.stubGlobal('EventSource', FakeEventSource);
});

describe('subscribeRun', () => {
	it('knows every event type of the contract', () => {
		const mapping = openapi.components.schemas.StreamEvent.discriminator.mapping;

		expect([...STREAM_EVENT_TYPES].sort()).toEqual(Object.keys(mapping).sort());
	});

	it('opens the run stream and listens to every event type', () => {
		subscribeRun('r1', () => {});

		expect(source().url).toBe('/api/chat/runs/r1/events');
		expect([...source().listeners.keys()].sort()).toEqual([...STREAM_EVENT_TYPES].sort());
	});

	it('passes parsed events on', () => {
		const onEvent = vi.fn();
		subscribeRun('r1', onEvent);

		source().emit({ ...base, type: 'text.delta', delta: 'Привет' });

		expect(onEvent).toHaveBeenCalledWith({ ...base, type: 'text.delta', delta: 'Привет' });
		expect(source().closed).toBe(false);
	});

	it('closes the stream after run.finished so the browser does not reconnect', () => {
		subscribeRun('r1', () => {});

		source().emit({ ...base, type: 'run.finished', status: 'done', message_id: null, error: null });

		expect(source().closed).toBe(true);
	});

	it('closes the stream on unsubscribe', () => {
		const unsubscribe = subscribeRun('r1', () => {});

		unsubscribe();

		expect(source().closed).toBe(true);
	});
});
