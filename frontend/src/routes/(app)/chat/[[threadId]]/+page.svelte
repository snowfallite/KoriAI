<script lang="ts">
	import { untrack } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import { toast } from 'svelte-sonner';
	import { goto, invalidate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, ok } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { LiveRun } from '$lib/state/run.svelte';
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import Composer from './components/Composer.svelte';
	import MessageView from './components/MessageView.svelte';
	import RunStatus from './components/RunStatus.svelte';
	import SuggestionFan from './components/SuggestionFan.svelte';
	import {
		SUGGESTIONS,
		canSend,
		greeting,
		isOver,
		questionCount,
		threadTitle,
		turns,
		type ErrorOut
	} from './logic';

	let { data } = $props();

	const thread = $derived(data.chat.kind === 'ready' ? data.chat.thread : null);
	const list = $derived(thread ? turns(thread.messages) : []);

	/** The question this page sent, until the thread from REST answers it. */
	let asked = $state<{
		thread: string;
		message: string;
		run: string;
		text: string;
		since: number;
	} | null>(null);
	// ?q= of the address fills the field (F-03 AC 10). A new load with the same ?q=, such as the
	// reload after an answer, leaves what the person types: a derived passes on changes only.
	const fromAddress = $derived(data.question);
	let draft = $derived(fromAddress);
	let sending = $state(false);
	let composer = $state<ReturnType<typeof Composer> | null>(null);
	/** The errors of runs that failed while the page watched, by the id of the failed answer. */
	const failures = new SvelteMap<string, ErrorOut>();
	/** The question sent from this thread, or from a new chat whose thread still loads. */
	const mine = $derived(asked && (!thread || asked.thread === thread.thread.id) ? asked : null);

	/** The run the page follows: the active run of the thread, or the one it just started. */
	const followed = $derived.by(() => {
		if (thread?.active_run) return thread.active_run.id;
		if (!mine) return null;
		const turn = list.find((found) => found.question.id === mine.message);
		return turn?.answer ? null : mine.run;
	});

	let live = $state<LiveRun | null>(null);

	$effect(() => {
		const runId = followed;
		if (!runId) return;
		const run = new LiveRun(runId);
		live = run;
		return () => {
			run.close();
			if (live === run) live = null;
		};
	});

	// The answer the stream showed is saved now: REST gives it with its blocks (tech.md §7).
	$effect(() => {
		const run = live;
		if (run && (isOver(run.view) || run.closed)) untrack(() => void settle(run));
	});

	const busy = $derived(live !== null && !isOver(live.view) && !live.closed);
	/** The question the live run answers: the one this page sent, else the last of the thread
	 * (a user has one active run, and it answers the newest question). */
	const liveQuestion = $derived.by(() => {
		const last = list.at(-1);
		if (!live || !last || last.answer) return null;
		if (mine && last.question.id !== mine.message) return null;
		return last.question.id;
	});
	/** A question sent from this page that the thread from REST does not show yet. */
	const pending = $derived(
		mine && live && !list.some((turn) => turn.question.id === mine.message) ? mine : null
	);

	async function settle(run: LiveRun) {
		const { message_id, error } = run.view;
		if (message_id && error) failures.set(message_id, error);
		await invalidate('app:chat');
		// A question sent meanwhile keeps its own mark.
		if (asked?.run === run.runId) asked = null;
	}

	async function send(text: string) {
		const question = text.trim();
		if (!canSend(question) || sending || busy) return;
		sending = true;
		try {
			const body = { thread_id: thread?.thread.id ?? null, text: question };
			const accepted = await ok(api.POST('/api/chat/messages', { body }));
			asked = {
				thread: accepted.thread_id,
				message: accepted.message_id,
				run: accepted.run_id,
				text: question,
				since: Date.now()
			};
			draft = '';
			if (accepted.thread_id === thread?.thread.id) {
				await invalidate('app:chat');
			} else {
				await goto(resolve(`/chat/${accepted.thread_id}`));
			}
		} catch (error) {
			toast.error((error as ApiError).message);
		} finally {
			sending = false;
		}
	}

	async function stop() {
		if (!followed) return;
		try {
			const path = { run_id: followed };
			await ok(api.POST('/api/chat/runs/{run_id}/cancel', { params: { path } }));
		} catch (error) {
			const failure = error as ApiError;
			// The run may end on its own meanwhile: its stream says how (409).
			if (failure.code !== 'conflict') toast.error(failure.message);
		}
	}

	function pick(question: string) {
		draft = question;
		composer?.focus();
	}
</script>

<svelte:head><title>{thread ? threadTitle(thread) : 'Чат'} · Kōri</title></svelte:head>

{#if data.chat.kind === 'missing'}
	<PageHeader title="Чат" />
	<div class="p-4 md:p-12">
		<EmptyState title="Чат не найден" description="Его удалили, или ссылка ведёт в чужой чат.">
			{#snippet action()}
				<Button href={resolve('/chat')}>
					<span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат
				</Button>
			{/snippet}
		</EmptyState>
	</div>
{:else if data.chat.kind === 'error'}
	<PageHeader title="Чат" />
	<div class="p-4 md:p-12">
		<ErrorState error={data.chat.error} onRetry={() => invalidate('app:chat')} />
	</div>
{:else if !thread && !pending}
	<!-- A new chat (kori-v4, chat-start): one big question, the white field, the fan. -->
	<PageHeader title="Новый чат" />
	<div class="flex justify-center px-4 pt-10 pb-8 md:px-12 md:pt-[72px] md:pb-14">
		<div class="w-full max-w-[820px]">
			<p class="mb-5 text-ui text-grey-300">{greeting(new Date(), data.me.user.display_name)}</p>
			<h2 class="text-quote md:text-display">
				Что с портфелем<br />и почему?<span
					aria-hidden="true"
					class="ml-[0.14em] inline-block h-[0.8em] w-[0.45em] animate-ki-caret bg-primary align-[-0.04em]"
				></span>
			</h2>
			<div class="mt-8 md:mt-12">
				<Composer bind:this={composer} bind:value={draft} variant="start" {sending} onSend={send} />
			</div>
			<SuggestionFan suggestions={SUGGESTIONS} onPick={pick} />
		</div>
	</div>
{:else}
	<!-- The thread fills the window under the header of a phone and over its tabs, so the field
	     stays at the bottom under a short thread too. -->
	<div class="flex min-h-[calc(100svh-7.5rem-env(safe-area-inset-bottom))] flex-col md:min-h-svh">
		<PageHeader
			title={thread ? threadTitle(thread) : (pending?.text ?? 'Чат')}
			description={questionCount(list.length + (pending ? 1 : 0))}
		/>
		<div class="flex flex-1 justify-center px-4 pt-8 pb-10 md:px-12 md:pt-12 md:pb-16">
			<div class="flex w-full max-w-[820px] flex-col gap-14 md:gap-[72px]">
				{#each list as turn (turn.question.id)}
					{#if live && turn.question.id === liveQuestion}
						<RunStatus
							number={turn.number}
							question={turn.question.content}
							since={mine?.since ?? Date.parse(turn.question.created_at)}
							run={live}
							onRetry={() => send(turn.question.content)}
						/>
					{:else}
						<MessageView
							{turn}
							error={turn.answer ? failures.get(turn.answer.id) : undefined}
							onRetry={() => send(turn.question.content)}
						/>
					{/if}
				{/each}
				{#if pending && live}
					<RunStatus
						number={list.length + 1}
						question={pending.text}
						since={pending.since}
						run={live}
						onRetry={() => send(pending.text)}
					/>
				{/if}
			</div>
		</div>
		<!-- The question field stays under the feed, above the tabs of a phone. -->
		<div
			class="sticky bottom-[calc(4rem+env(safe-area-inset-bottom))] flex justify-center border-t bg-background px-4 pt-3 pb-3 md:bottom-0 md:px-12 md:pt-5 md:pb-7"
		>
			<div class="w-full max-w-[820px]">
				<Composer
					bind:value={draft}
					variant="thread"
					{busy}
					{sending}
					onSend={send}
					onStop={stop}
				/>
			</div>
		</div>
	</div>
{/if}
