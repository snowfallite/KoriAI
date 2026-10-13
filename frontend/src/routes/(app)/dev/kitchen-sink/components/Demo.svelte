<script lang="ts">
	import type { Snippet } from 'svelte';

	let { name, note, children }: { name: string; note?: string; children: Snippet } = $props();
</script>

<!-- A sheet of the kitchen-sink: a caption over a hairline, as the sheets of the v3 mockup. -->
<section aria-label={name} class="space-y-4">
	<header class="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b pb-3">
		<h2 class="text-caption uppercase">{name}</h2>
		{#if note}
			<p class="text-caption text-grey-600">{note}</p>
		{/if}
	</header>
	{@render children()}
</section>
