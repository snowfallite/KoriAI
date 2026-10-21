<script lang="ts">
	import type { Snippet } from 'svelte';

	let { name, note, children }: { name: string; note?: string; children: Snippet } = $props();
</script>

<!-- A sheet of the kitchen-sink as the system page of v4 sets it: a bold heading, a grey note. -->
<section aria-label={name} class="space-y-4">
	<header class="space-y-1.5">
		<h2 class="text-[14px]/5 font-bold">{name}</h2>
		{#if note}
			<p class="text-ui text-grey-600">{note}</p>
		{/if}
	</header>
	{@render children()}
</section>
