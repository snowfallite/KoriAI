<script lang="ts">
	import ArtifactView from '$lib/components/ArtifactView.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import type { LiveRun } from '$lib/state/run.svelte';
	import * as Alert from '$lib/ui/alert';
	import { Button } from '$lib/ui/button';
	import { splitBlocks } from '$lib/utils/blocks';
	import { isOver, runFailure, runLabel } from '../logic';
	import QuestionStrip from './QuestionStrip.svelte';

	let {
		number,
		question,
		since,
		run,
		onRetry
	}: {
		number: number;
		question: string;
		/** When the question went: the strip counts the seconds of the run from it */
		since: number;
		run: LiveRun;
		onRetry: () => void;
	} = $props();

	const view = $derived(run.view);
	// A closed stream says the run is over, not how: the thread from REST tells that.
	const over = $derived(isOver(view) || run.closed);
	// A shutdown ended the run before its answer (§3.4).
	const interrupted = $derived(view.status === 'interrupted');
	// The stream shows the blocks the saved answer will have (tech.md §6.6, §9.9).
	const blocks = $derived(
		splitBlocks(view.text, new Map(view.artifacts.map((a) => [a.local_id, a.id]))).blocks
	);
	const artifacts = $derived(new Map(view.artifacts.map((a) => [a.id, a])));
	let now = $state(Date.now());

	$effect(() => {
		if (over) return;
		const timer = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(timer);
	});
</script>

<!-- A running question (kori-v4, chat-thread): the strip on the gradient with the queue or the
     step and its seconds, the answer as it streams, the red caret at its end. -->
<article aria-label="Вопрос {number}, ответ готовится" aria-busy={!over} class="flex flex-col">
	<QuestionStrip
		{number}
		text={question}
		running={!over}
		aside={over ? undefined : runLabel(view, (now - since) / 1000)}
	/>
	{#if interrupted}
		<Alert.Root class="mt-6 border-l-grey-600">
			<Alert.Title>Ответ прерван</Alert.Title>
		</Alert.Root>
		<div class="mt-4"><Button variant="link" onclick={onRetry}>Повторить</Button></div>
	{:else if view.status === 'failed'}
		<div class="mt-6"><ErrorState error={runFailure(view.error)} {onRetry} /></div>
	{:else}
		<div class="mt-7 flex flex-col gap-7">
			{#each blocks as block, n (n)}
				{#if block.type === 'markdown'}
					<Markdown source={block.text} sources={view.sources} streaming={!over} />
				{:else}
					{@const artifact = artifacts.get(block.artifact_id)}
					{#if artifact}<ArtifactView {artifact} />{/if}
				{/if}
			{/each}
			{#if !over}
				<span
					aria-hidden="true"
					class="inline-block h-[1.05em] w-[0.55em] animate-ki-caret bg-primary text-base"
				></span>
			{/if}
		</div>
	{/if}
</article>
