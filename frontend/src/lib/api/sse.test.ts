import { beforeEach, describe, expect, it, vi } from 'vitest';
import openapi from './openapi.json';
import { STREAM_EVENT_TYPES, subscribeRun } from './sse';

type Listener = (event: Event) => void;

/** The parts of EventSource the stream uses, with the ready states of the browser. */
class FakeEventSource {
	static readonly CONNECTING = 0;
	static readonly OPEN = 1;
	static readonly CLOSED = 2;
	static last: FakeEventSource | undefined;
	readonly listeners = new Map<string, Listener>();
	readyState = FakeEventSource.CONNECTING;
	closed = false;

	constructor(readonly url: string) {
		FakeEventSource.last = this;
	}

	addEventListener(type: string, listener: Listener) {
		this.listeners.set(type, listener);
	}

	close() {
		this.closed = true;
		this.readyState = FakeEventSource.CLOSED;
	}

	emit(data: { type: string; [field: string]: unknown }) {
		this.readyState = FakeEventSource.OPEN;
		this.listeners.get(data.type)?.(new MessageEvent(data.type, { data: JSON.stringify(data) }));
	}

	/** What the browser does when a connection breaks (CONNECTING: it tries again) or when the
	 * server refuses it with a status other than 200 (CLOSED: it gives up). */
	fail(readyState: number) {
		this.readyState = readyState;
		this.listeners.get('error')?.(new Event('error'));
	}
}

function source(): FakeEventSource {
	if (!FakeEventSource.last) throw new Error('no EventSource opened');
	return FakeEventSource.last;
}

const base = { seq: 1, run_id: 'r1', ts: '2026-09-29T00:00:00Z' };
const finished = { ...base, type: 'run.finished', status: 'done', message_id: null, error: null };

beforeEach(() => {
	FakeEventSource.last = undefined;
	vi.stubGlobal('EventSource', FakeEventSource);
});

describe('subscribeRun', () => {
	it('knows every event type of the contract', () => {
		const mapping = openapi.components.schemas.StreamEvent.discriminator.mapping;

		expect([...STREAM_EVENT_TYPES].sort()).toEqual(Object.keys(mapping).sort());
	});

	it('opens the run stream and listens to every event type and to errors', () => {
		subscribeRun('r1', () => {});

		expect(source().url).toBe('/api/chat/runs/r1/events');
		expect([...source().listeners.keys()].sort()).toEqual([...STREAM_EVENT_TYPES, 'error'].sort());
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

		source().emit(finished);

		expect(source().closed).toBe(true);
	});

	it('closes the stream on unsubscribe', () => {
		const unsubscribe = subscribeRun('r1', () => {});

		unsubscribe();

		expect(source().closed).toBe(true);
	});

	it('tells once that the server refused the stream (404 after a restart, 410 later)', () => {
		const onClosed = vi.fn();
		subscribeRun('r1', () => {}, onClosed);

		source().fail(FakeEventSource.CLOSED);
		source().fail(FakeEventSource.CLOSED);

		expect(onClosed).toHaveBeenCalledOnce();
	});

	it('waits quietly while the browser tries to reconnect', () => {
		const onClosed = vi.fn();
		subscribeRun('r1', () => {}, onClosed);

		source().emit({ ...base, type: 'run.started' });
		source().fail(FakeEventSource.CONNECTING);

		expect(onClosed).not.toHaveBeenCalled();
	});

	it('stays silent after run.finished and after unsubscribe', () => {
		const onClosed = vi.fn();
		subscribeRun('r1', () => {}, onClosed);
		source().emit(finished);
		source().fail(FakeEventSource.CLOSED);

		const unsubscribe = subscribeRun('r2', () => {}, onClosed);
		unsubscribe();
		source().fail(FakeEventSource.CLOSED);

		expect(onClosed).not.toHaveBeenCalled();
	});

	it('takes no callback for closing', () => {
		subscribeRun('r1', () => {});

		expect(() => source().fail(FakeEventSource.CLOSED)).not.toThrow();
	});
});
