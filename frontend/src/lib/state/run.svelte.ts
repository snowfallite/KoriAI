import { subscribeRun } from '$lib/api/sse';
import { initialRun, reduceRunEvent, type RunView } from '$lib/utils/stream-reducer';

/** A run as its SSE stream shows it (tech.md §7); the stream closes itself on run.finished. */
export class LiveRun {
	view = $state.raw<RunView>(initialRun());
	/** The server ended the stream without run.finished (a restart, an expired buffer): the run
	 * is over and the thread from REST tells how. */
	closed = $state(false);
	/** Stops listening, e.g. when the page goes away mid-run. */
	readonly close: () => void;

	constructor(readonly runId: string) {
		this.close = subscribeRun(
			runId,
			(event) => {
				this.view = reduceRunEvent(this.view, event);
			},
			() => {
				this.closed = true;
			}
		);
	}
}
