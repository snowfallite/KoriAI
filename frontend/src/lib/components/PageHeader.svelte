<script lang="ts">
	import type { Snippet } from 'svelte';

	let { title, description, actions }: { title: string; description?: string; actions?: Snippet } =
		$props();
</script>

<header class="flex flex-wrap items-end justify-between gap-3 border-b pb-4">
	<div class="min-w-0 space-y-1">
		<h1 class="text-lg font-medium">{title}</h1>
		{#if description}
			<p class="text-xs text-muted-foreground">{description}</p>
		{/if}
	</div>
	{#if actions}
		<div class="flex items-center gap-2">{@render actions()}</div>
	{/if}
</header>
