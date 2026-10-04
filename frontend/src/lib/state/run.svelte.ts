import { subscribeRun } from '$lib/api/sse';
import { initialRun, reduceRunEvent, type RunView } from '$lib/utils/stream-reducer';

/** A run as its SSE stream shows it (tech.md §7); the stream closes itself on run.finished. */
export class LiveRun {
	view = $state.raw<RunView>(initialRun());
	/** Stops listening, e.g. when the page goes away mid-run. */
	readonly close: () => void;

	constructor(runId: string) {
		this.close = subscribeRun(runId, (event) => {
			this.view = reduceRunEvent(this.view, event);
		});
	}
}
