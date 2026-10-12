<script lang="ts">
	import type { Snippet } from 'svelte';

	let { title, description, actions }: { title: string; description?: string; actions?: Snippet } =
		$props();
</script>

<!-- The meta line of v3 (tech.md §13.2): 56 px of caps over a hairline, the title in h1, the note
     in grey, the actions on the right. Without actions the kana of the brand keep the right edge. -->
<header
	class="flex min-h-14 flex-wrap items-center justify-between gap-x-8 gap-y-2 border-b px-4 py-3 text-caps tracking-[0.04em] uppercase md:px-12"
>
	<h1>{title}</h1>
	{#if description}
		<p class="text-grey-600">{description}</p>
	{/if}
	{#if actions}
		<div class="flex flex-wrap items-center gap-2">{@render actions()}</div>
	{:else}
		<span
			lang="ja"
			aria-hidden="true"
			class="hidden font-sans font-light tracking-[0.6em] text-grey-600 normal-case md:inline"
			>こおり</span
		>
	{/if}
</header>
