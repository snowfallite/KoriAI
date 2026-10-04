import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { ArtifactOut, SourceRef, StreamEvent } from '$lib/types';
import { initialRun, reduceRunEvent } from './stream-reducer';

// An event as its publisher writes it: the bus stamps seq, run_id and ts.
type Body = StreamEvent extends infer E
	? E extends StreamEvent
		? Omit<E, 'seq' | 'run_id' | 'ts'>
		: never
	: never;

const RUN = '0199a1b2-0000-7000-8000-000000000001';
const TS = '2026-10-04T10:00:00Z';

function stamp(bodies: Body[]): StreamEvent[] {
	return bodies.map((body, i) => ({ ...body, seq: i + 1, run_id: RUN, ts: TS }) as StreamEvent);
}

function fold(events: StreamEvent[]) {
	return events.reduce(reduceRunEvent, initialRun());
}

const finished: Body = { type: 'run.finished', status: 'done', message_id: null, error: null };
const callId = fc.constantFrom('call-1', 'call-2');

const body: fc.Arbitrary<Body> = fc.oneof(
	fc.string().map((delta): Body => ({ type: 'text.delta', delta })),
	fc.constant<Body>({ type: 'text.reset' }),
	fc.nat(5).map((position): Body => ({ type: 'run.queued', position })),
	fc.constant<Body>({ type: 'run.started' }),
	fc.nat(9).map((step): Body => ({ type: 'step.started', step })),
	callId.map((call_id): Body => ({
		type: 'tool.started',
		step: 1,
		call_id,
		tool: 'calc',
		title: 'Считаю'
	})),
	fc.tuple(callId, fc.boolean()).map(([call_id, ok]): Body => ({
		type: 'tool.finished',
		step: 1,
		call_id,
		tool: 'calc',
		ok,
		summary: ok ? '25' : 'Выражение не разобрано',
		error_code: ok ? null : 'validation_error',
		duration_ms: 3
	})),
	fc.constant<Body>({ type: 'run.warning', code: 'steps_limit', message: 'Лимит шагов' }),
	fc.dictionary(fc.string(), fc.integer()).map((payload): Body => ({ type: 'dev.echo', payload })),
	fc.constant(finished)
);

describe('reduceRunEvent', () => {
	it('ignores an event it has seen: seq <= last_seq changes nothing', () => {
		fc.assert(
			fc.property(fc.array(body, { minLength: 1 }), fc.nat(), (bodies, pick) => {
				const events = stamp(bodies);
				const run = fold(events);
				const seen = events[pick % events.length] as StreamEvent;

				expect(reduceRunEvent(run, seen)).toBe(run);
			})
		);
	});

	it('ends with the same state when a reconnect replays events again', () => {
		fc.assert(
			fc.property(fc.array(body), fc.nat(), fc.nat(), (bodies, cut, back) => {
				const events = stamp(bodies);
				const k = cut % (events.length + 1);
				const replayFrom = back % (k + 1);

				const replayed = [...events.slice(0, k), ...events.slice(replayFrom)];

				expect(fold(replayed)).toEqual(fold(events));
			})
		);
	});

	it('keeps the text of the deltas after the last text.reset', () => {
		fc.assert(
			fc.property(fc.array(body), (bodies) => {
				const tail = bodies.slice(bodies.findLastIndex((b) => b.type === 'text.reset') + 1);
				const text = tail.map((b) => (b.type === 'text.delta' ? b.delta : '')).join('');

				expect(fold(stamp(bodies)).text).toBe(text);
			})
		);
	});

	it('returns the payload of dev.echo and the final status', () => {
		const run = fold(stamp([{ type: 'dev.echo', payload: { text: 'Привет' } }, finished]));

		expect(run).toMatchObject({ echo: { text: 'Привет' }, status: 'done', last_seq: 2 });
	});

	it('shows the queue position until the run moves on', () => {
		const queued = fold(stamp([{ type: 'run.queued', position: 2 }]));
		const started = fold(stamp([{ type: 'run.queued', position: 2 }, { type: 'run.started' }]));

		expect([queued.position, queued.status]).toEqual([2, 'queued']);
		expect([started.position, started.status]).toEqual([null, 'running']);
	});

	it('puts every event into its field', () => {
		const source: SourceRef = {
			local_id: 's1',
			kind: 'tinvest',
			title: 'Т-Инвестиции',
			url: null,
			publisher: null,
			published_at: null,
			document_id: null,
			page: null,
			snippet: null
		};
		const artifact: ArtifactOut = {
			id: '0199a1b2-0000-7000-8000-000000000002',
			local_id: 't1',
			kind: 'table',
			spec: {
				title: 'Позиции',
				columns: [{ key: 'ticker', label: 'Тикер', type: 'text', currency: null, digits: null }],
				rows: [{ ticker: 'SBER' }],
				total: null,
				note: null,
				instruments: {},
				source_ids: ['s1']
			},
			image_url: null,
			created_at: TS
		};
		const error = { code: 'internal', message: 'Сбой', details: null, request_id: 'r1' } as const;

		const run = fold(
			stamp([
				{ type: 'run.started' },
				{
					type: 'run.routed',
					intent: 'portfolio_status',
					family: 'lite',
					model_id: 'GigaChat-2',
					reason: 'Портфель'
				},
				{ type: 'step.started', step: 1 },
				{
					type: 'tool.started',
					step: 1,
					call_id: 'c',
					tool: 'portfolio_overview',
					title: 'Загружаю портфель'
				},
				{ type: 'source.added', source },
				{ type: 'artifact.created', artifact },
				{
					type: 'tool.finished',
					step: 1,
					call_id: 'c',
					tool: 'portfolio_overview',
					ok: true,
					summary: '12 позиций',
					error_code: null,
					duration_ms: 40
				},
				{ type: 'run.warning', code: 'model_downgraded', message: 'Модель понижена' },
				{ type: 'run.finished', status: 'failed', message_id: null, error }
			])
		);

		expect(run).toEqual({
			last_seq: 9,
			status: 'failed',
			position: null,
			routed: {
				intent: 'portfolio_status',
				family: 'lite',
				model_id: 'GigaChat-2',
				reason: 'Портфель'
			},
			step: 1,
			tools: [
				{
					call_id: 'c',
					step: 1,
					tool: 'portfolio_overview',
					title: 'Загружаю портфель',
					result: { ok: true, summary: '12 позиций', error_code: null, duration_ms: 40 }
				}
			],
			artifacts: [artifact],
			sources: [source],
			text: '',
			warnings: [{ code: 'model_downgraded', message: 'Модель понижена' }],
			echo: null,
			message_id: null,
			error
		});
	});
});
