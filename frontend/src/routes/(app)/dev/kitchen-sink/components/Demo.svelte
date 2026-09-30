<script lang="ts">
	import type { Snippet } from 'svelte';

	let { name, note, children }: { name: string; note?: string; children: Snippet } = $props();
</script>

<section aria-label={name} class="space-y-3 border-t pt-4">
	<header class="flex flex-wrap items-baseline gap-x-3">
		<h2 class="text-sm font-medium">{name}</h2>
		{#if note}
			<p class="text-xs text-muted-foreground">{note}</p>
		{/if}
	</header>
	{@render children()}
</section>
