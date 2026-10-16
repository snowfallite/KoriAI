<script lang="ts">
	import type { Snippet } from 'svelte';
	import Logo from '$lib/components/Logo.svelte';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';

	let {
		title,
		note,
		error = null,
		onsubmit,
		fields,
		actions
	}: {
		title: string;
		/** The caption across from the seal: how the panel lets the person in. */
		note: string;
		/** An error of the whole form, such as too many attempts: a note above the fields. */
		error?: ApiError | null;
		onsubmit: (event: SubmitEvent) => void;
		fields: Snippet;
		actions: Snippet;
	} = $props();

	const id = $props.id();
</script>

<!-- A white panel where a person acts (tech.md §13.3): the seal, a black title strip with a red
     arrow, the fields, a strip of two buttons flush with the bottom. -->
<form
	aria-labelledby="{id}-title"
	class="theme-day w-full max-w-[440px] bg-background text-foreground"
	{onsubmit}
>
	<div class="flex h-12 items-center justify-between gap-4 px-3.5 md:h-[52px] md:px-4">
		<Logo size="sm" />
		<span class="text-[10px] tracking-[0.06em] text-grey-600 uppercase md:text-caption">{note}</span
		>
	</div>
	<h1
		id="{id}-title"
		class="flex items-center justify-between bg-foreground px-3.5 py-3 text-[24px]/7 text-background md:px-4 md:py-3.5 md:text-[28px]/8"
	>
		{title}<span aria-hidden="true" class="text-[18px] text-primary md:text-[20px]">↓</span>
	</h1>
	<div class="flex flex-col gap-4 px-3.5 pt-[18px] pb-5 md:gap-5 md:px-4 md:pt-6 md:pb-7">
		{#if error}
			<Alert.Root variant="destructive">
				<span data-slot="alert-glyph" aria-hidden="true">×</span>
				<Alert.Title>{error.message}</Alert.Title>
			</Alert.Root>
		{/if}
		{@render fields()}
	</div>
	<div class="flex flex-wrap">{@render actions()}</div>
</form>
