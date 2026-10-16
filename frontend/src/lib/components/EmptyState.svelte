<script lang="ts">
	import type { Component, Snippet } from 'svelte';

	// The icon stays in the props of tech.md §13.2, but v3 draws none: the title carries the state.
	// eslint-disable-next-line svelte/no-unused-props -- the contract keeps icon
	let {
		title,
		description,
		action
	}: {
		icon?: Component<{ class?: string }>;
		title: string;
		description?: string;
		action?: Snippet;
	} = $props();
</script>

<!-- A frame without fill (kori-v3, Карточки): a 28 px title, a grey note, the main action. -->
<div class="flex flex-col items-start gap-4 border px-8 py-10">
	<p class="text-[28px]/8">{title}</p>
	{#if description}
		<p class="max-w-[52ch] text-[14px]/[22px] text-muted-foreground">{description}</p>
	{/if}
	{#if action}
		<div class="mt-2">{@render action()}</div>
	{/if}
</div>
