<script lang="ts">
	import type { Snippet } from 'svelte';

	let { title, description, actions }: { title: string; description?: string; actions?: Snippet } =
		$props();
</script>

<!-- The meta line of v4 (tech.md §13.2): 56 px over a hairline, the title in normal case in h1,
     the note in grey, the actions on the right; no decor. -->
<header
	class="flex min-h-14 flex-wrap items-center justify-between gap-x-8 gap-y-2 border-b px-4 py-3 md:px-12"
>
	<h1 class="text-lead">{title}</h1>
	{#if description}
		<p class="text-caps text-grey-600">{description}</p>
	{/if}
	{#if actions}
		<div class="flex flex-wrap items-center gap-2">{@render actions()}</div>
	{/if}
</header>
