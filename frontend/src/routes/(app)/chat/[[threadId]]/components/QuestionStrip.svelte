<script lang="ts">
	import { cn } from '$lib/utils/cn';

	let {
		number,
		text,
		aside,
		running = false
	}: {
		number: number;
		text: string;
		/** The time of the question, or the queue and the step of a running one */
		aside?: string;
		running?: boolean;
	} = $props();
</script>

<!-- The question in the feed (kori-v4, chat-thread): its number in a cell, the words on a light
     strip, the time on the right. A running one stands on the gradient of the AI at work with a
     line running under it. -->
<div>
	<div class={cn('flex min-h-11 items-stretch text-black', running ? 'ki-fade' : 'bg-grey-200')}>
		<span
			aria-hidden="true"
			class={cn('grid w-11 shrink-0 place-items-center text-[14px]', !running && 'bg-grey-400')}
			>{number}</span
		>
		<p
			class={cn(
				'flex min-w-0 flex-1 items-center py-2.5 text-lead break-words',
				running ? 'pr-4' : 'px-4'
			)}
		>
			{text}
		</p>
		{#if aside}
			<span
				class={cn(
					'flex shrink-0 items-center px-3.5',
					running ? 'text-caps' : 'bg-grey-100 text-caption'
				)}>{aside}</span
			>
		{/if}
	</div>
	{#if running}
		<div aria-hidden="true" class="relative h-0.5 overflow-hidden bg-border">
			<span class="absolute inset-y-0 left-0 w-[30%] animate-ki-scan bg-primary"></span>
		</div>
	{/if}
</div>
