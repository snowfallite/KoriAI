<script lang="ts">
	import type { Component, Snippet } from 'svelte';

	let {
		icon: Icon,
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

<div class="flex flex-col items-center gap-3 border border-dashed px-6 py-10 text-center">
	{#if Icon}
		<div class="grid size-9 place-items-center bg-muted text-muted-foreground" aria-hidden="true">
			<Icon class="size-4" />
		</div>
	{/if}
	<div class="space-y-1">
		<p class="text-sm font-medium">{title}</p>
		{#if description}
			<p class="max-w-sm text-xs text-muted-foreground">{description}</p>
		{/if}
	</div>
	{@render action?.()}
</div>
