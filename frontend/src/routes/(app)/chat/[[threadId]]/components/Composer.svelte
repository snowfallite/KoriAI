<script lang="ts">
	import { Button } from '$lib/ui/button';
	import { Textarea } from '$lib/ui/textarea';
	import { cn } from '$lib/utils/cn';
	import { MAX_QUESTION, canSend, sendsOnKey } from '../logic';

	let {
		value = $bindable(''),
		variant,
		busy = false,
		sending = false,
		onSend,
		onStop
	}: {
		value?: string;
		/** The big field of a new chat, or the line under a thread */
		variant: 'start' | 'thread';
		/** A run goes: the field offers to stop it instead of sending */
		busy?: boolean;
		/** The question is on its way */
		sending?: boolean;
		onSend: (text: string) => void;
		onStop?: () => void;
	} = $props();

	const id = $props.id();
	let field = $state<HTMLTextAreaElement | null>(null);
	const ready = $derived(canSend(value) && !busy && !sending);
	const near = $derived(value.length > MAX_QUESTION - 400);

	/** The fan of a new chat puts its question here and hands the focus over. */
	export function focus() {
		field?.focus();
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (ready) onSend(value);
	}

	function keydown(event: KeyboardEvent) {
		if (!sendsOnKey(event)) return;
		// Enter never breaks the line: Shift+Enter does (F-03 AC 8).
		event.preventDefault();
		if (ready) onSend(value);
	}
</script>

{#snippet send()}
	<Button type="submit" variant="ai" size="icon" aria-label="Спросить" disabled={!ready}>→</Button>
{/snippet}

<!-- The white panel where the question is asked (tech.md §13.3, kori-v4): the focus ring goes
     around the panel in the colors of the page, the field has no frame of its own. -->
<div class="focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ring">
	<form
		aria-label={variant === 'start' ? 'Новый вопрос' : 'Уточнение'}
		class={cn(
			'theme-day border bg-background text-foreground',
			variant === 'thread' && 'flex items-end gap-2 p-1.5'
		)}
		onsubmit={submit}
	>
		<label for="{id}-question" class="sr-only">
			{variant === 'start' ? 'Вопрос' : 'Уточнить вопрос'}
		</label>
		<Textarea
			id="{id}-question"
			bind:ref={field}
			bind:value
			rows={variant === 'start' ? 2 : 1}
			maxlength={MAX_QUESTION}
			placeholder={variant === 'start'
				? 'Например: почему Газпром дешевле цены покупки'
				: 'Уточните вопрос'}
			onkeydown={keydown}
			class={cn(
				'min-h-0 resize-none border-0 bg-transparent focus:shadow-none in-[.theme-day]:bg-transparent',
				variant === 'start'
					? 'px-5 pt-5 pb-1 text-lead/[26px] md:text-lead/[26px]'
					: 'max-h-48 min-w-0 flex-1 px-2.5 py-2 text-base/6 md:text-base/6'
			)}
		/>
		{#if variant === 'start'}
			<div class="flex items-center justify-between gap-4 pt-2 pr-3 pb-3 pl-5">
				<span class="text-caps text-grey-600">Enter отправит вопрос</span>
				{@render send()}
			</div>
		{:else if busy}
			<Button variant="secondary" class="shrink-0" onclick={onStop}>
				<span data-slot="button-glyph" aria-hidden="true">×</span>Остановить
			</Button>
		{:else}
			<div class="shrink-0">{@render send()}</div>
		{/if}
	</form>
</div>
{#if near}
	<p class="mt-1.5 text-right text-caption text-grey-600" aria-live="polite">
		{value.length} из {MAX_QUESTION}
	</p>
{/if}
