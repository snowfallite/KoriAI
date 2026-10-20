<script lang="ts" module>
	// A field of the panel: 52 px, the --muted fill of a white panel, 16 px text (kori-v4).
	export const FIELD = 'h-[52px] px-3.5 text-base md:px-4 md:text-base';
	// The one action of the panel: 56 px, the glyph cell and the label 18 px after it.
	export const ACTION =
		'h-14 w-full justify-start border-0 text-[14px] has-[>[data-slot=button-glyph]]:gap-[18px] [&>[data-slot=button-glyph]]:text-lg';
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { cn } from '$lib/utils/cn';

	let {
		title,
		error = null,
		compact = false,
		onsubmit,
		fields,
		action,
		footer
	}: {
		title: string;
		/** An error of the whole form, such as too many attempts: a notice above the fields. */
		error?: ApiError | null;
		/** The longer registration form: a step less air (kori-v4, register.html). */
		compact?: boolean;
		onsubmit: (event: SubmitEvent) => void;
		fields: Snippet;
		action: Snippet;
		/** The way to the other page, under the action. */
		footer: Snippet;
	} = $props();

	const id = $props.id();
</script>

<!-- The white panel where a person acts (tech.md §13.3, kori-v4): a 3 px stripe of the brand on
     top, the title, the fields, one action and the way to the other page under it. -->
<form
	aria-labelledby="{id}-title"
	class={cn(
		'theme-day w-full max-w-[460px] bg-background px-5 pt-7 pb-6 text-foreground md:px-10',
		compact ? 'md:pt-9 md:pb-7' : 'md:pt-10 md:pb-8'
	)}
	{onsubmit}
>
	<div
		aria-hidden="true"
		class={cn(
			'-mx-5 -mt-7 mb-[25px] h-[3px] bg-linear-to-r from-primary via-pink via-40% to-transparent md:-mx-10',
			compact ? 'md:-mt-9 md:mb-[33px]' : 'md:-mt-10 md:mb-[37px]'
		)}
	></div>
	<h1 id="{id}-title" class="text-[28px]/8 tracking-[-0.01em] md:text-quote">{title}</h1>
	<div
		class={cn('mt-6 flex flex-col gap-4', compact ? 'md:mt-7 md:gap-[18px]' : 'md:mt-8 md:gap-5')}
	>
		{#if error}
			<Alert.Root variant="destructive">
				<Alert.Title>{error.message}</Alert.Title>
			</Alert.Root>
		{/if}
		{@render fields()}
	</div>
	<div class={cn('mt-6', compact ? 'md:mt-[26px]' : 'md:mt-7')}>{@render action()}</div>
	<p
		class={cn(
			'mt-4 text-ui text-grey-600 [&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-primary-deep',
			compact ? 'md:mt-[18px]' : 'md:mt-5'
		)}
	>
		{@render footer()}
	</p>
</form>
