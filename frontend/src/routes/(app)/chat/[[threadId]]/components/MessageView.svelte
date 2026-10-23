<script lang="ts">
	import { toast } from 'svelte-sonner';
	import ArtifactView from '$lib/components/ArtifactView.svelte';
	import Disclaimer from '$lib/components/Disclaimer.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import SourceList from '$lib/components/SourceList.svelte';
	import * as Alert from '$lib/ui/alert';
	import { Button } from '$lib/ui/button';
	import { formatTime } from '$lib/utils/format';
	import { copyText, runFailure, took, type ErrorOut, type Turn } from '../logic';
	import QuestionStrip from './QuestionStrip.svelte';

	let {
		turn,
		error,
		onRetry
	}: {
		turn: Turn;
		/** The error of the run while this page watched it fail */
		error?: ErrorOut;
		/** Sends the same question again as a new message (F-03 AC 5) */
		onRetry: () => void;
	} = $props();

	const answer = $derived(turn.answer);
	const artifacts = $derived(new Map(answer?.artifacts.map((a) => [a.id, a]) ?? []));
	const tags = $derived(
		answer && answer.meta.model_id ? [answer.meta.model_id, took(turn.question, answer)] : []
	);
	let copied = $state(false);

	async function copy(text: string) {
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			toast.error('Не удалось скопировать');
			return;
		}
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
</script>

<!-- A question and its answer (kori-v4, chat-thread): the strip, the tags of the run without a
     seal, the answer in serif with its sources, the disclaimer and the actions. -->
<article aria-label="Вопрос {turn.number} и ответ" class="flex flex-col">
	<QuestionStrip
		number={turn.number}
		text={turn.question.content}
		aside={formatTime(turn.question.created_at)}
	/>
	{#if !answer}
		<!-- The run ended without an answer: the process restarted (F-03 AC 7). -->
		<Alert.Root class="mt-6 border-l-grey-600">
			<Alert.Title>Ответ прерван</Alert.Title>
		</Alert.Root>
		<div class="mt-4"><Button variant="link" onclick={onRetry}>Повторить</Button></div>
	{:else if answer.status === 'failed'}
		<div class="mt-6"><ErrorState error={runFailure(error)} {onRetry} /></div>
	{:else}
		{#if tags.length}
			<ul
				aria-label="Как получен ответ"
				class="mt-3 flex flex-wrap text-caption text-muted-foreground"
			>
				{#each tags as tag, n (n)}
					<li class="-ml-px flex h-6 items-center border border-grey-600 px-2 first:ml-0">{tag}</li>
				{/each}
			</ul>
		{/if}
		<div class="mt-7 flex flex-col gap-7">
			{#each answer.blocks as block, n (n)}
				{#if block.type === 'markdown'}
					<Markdown source={block.text} sources={answer.sources} />
				{:else}
					{@const artifact = artifacts.get(block.artifact_id)}
					{#if artifact}<ArtifactView {artifact} />{/if}
				{/if}
			{/each}
		</div>
		{#if answer.status === 'partial'}
			<Alert.Root class="mt-6 border-l-grey-600">
				<Alert.Title>Ответ остановлен</Alert.Title>
			</Alert.Root>
		{/if}
		{#if answer.sources.length}
			<div class="mt-9"><SourceList sources={answer.sources} /></div>
		{/if}
		{#if answer.meta.disclaimer}
			<div class="mt-5"><Disclaimer /></div>
		{/if}
		<div class="mt-4 flex gap-5">
			{#if answer.blocks.length}
				<Button variant="link" onclick={() => copy(copyText(answer))}>
					{copied ? 'Скопировано' : 'Копировать'}
				</Button>
			{/if}
			<Button variant="link" onclick={onRetry}>Повторить</Button>
		</div>
	{/if}
</article>
