import type { ArtifactOut, SourceRef, StreamEvent } from '$lib/types';

type EventOf<T extends StreamEvent['type']> = Extract<StreamEvent, { type: T }>;
type Finished = EventOf<'run.finished'>;
type ToolFinished = EventOf<'tool.finished'>;

type ToolStep = Pick<EventOf<'tool.started'>, 'call_id' | 'step' | 'tool' | 'title'> & {
	/** null while the tool runs */
	result: Pick<ToolFinished, 'ok' | 'summary' | 'error_code' | 'duration_ms'> | null;
};

/** What the SSE stream of a run has told so far (tech.md §7). */
export type RunView = {
	last_seq: number;
	status: Finished['status'];
	/** Place in the LLM queue while the run waits for it */
	position: number | null;
	routed: Pick<EventOf<'run.routed'>, 'intent' | 'family' | 'model_id' | 'reason'> | null;
	step: number;
	tools: ToolStep[];
	artifacts: ArtifactOut[];
	sources: SourceRef[];
	/** The deltas after the last text.reset */
	text: string;
	warnings: Pick<EventOf<'run.warning'>, 'code' | 'message'>[];
	/** The payload of dev.echo (dev and ci only) */
	echo: EventOf<'dev.echo'>['payload'] | null;
	message_id: string | null;
	error: Finished['error'];
};

export function initialRun(): RunView {
	return {
		last_seq: 0,
		status: 'queued',
		position: null,
		routed: null,
		step: 0,
		tools: [],
		artifacts: [],
		sources: [],
		text: '',
		warnings: [],
		echo: null,
		message_id: null,
		error: null
	};
}

/** Pure. An event the run has seen (seq <= last_seq, a replay after a reconnect) changes nothing. */
export function reduceRunEvent(run: RunView, event: StreamEvent): RunView {
	if (event.seq <= run.last_seq) return run;
	// The queue position holds only until the next event: then the run has its slot.
	const next: RunView = { ...run, last_seq: event.seq, position: null };
	switch (event.type) {
		case 'run.queued':
			return { ...next, position: event.position };
		case 'run.started':
			return { ...next, status: 'running' };
		case 'run.routed': {
			const { intent, family, model_id, reason } = event;
			return { ...next, routed: { intent, family, model_id, reason } };
		}
		case 'step.started':
			return { ...next, step: event.step };
		case 'tool.started': {
			const { call_id, step, tool, title } = event;
			return { ...next, tools: [...run.tools, { call_id, step, tool, title, result: null }] };
		}
		case 'tool.finished': {
			const { call_id, ok, summary, error_code, duration_ms } = event;
			const result = { ok, summary, error_code, duration_ms };
			const tools = run.tools.map((t) => (t.call_id === call_id ? { ...t, result } : t));
			return { ...next, tools };
		}
		case 'artifact.created':
			return { ...next, artifacts: [...run.artifacts, event.artifact] };
		case 'source.added':
			return { ...next, sources: [...run.sources, event.source] };
		case 'text.delta':
			return { ...next, text: run.text + event.delta };
		case 'text.reset':
			return { ...next, text: '' };
		case 'run.warning':
			return { ...next, warnings: [...run.warnings, { code: event.code, message: event.message }] };
		case 'run.finished': {
			const { status, message_id, error } = event;
			return { ...next, status, message_id, error };
		}
		case 'dev.echo':
			return { ...next, echo: event.payload };
	}
}
