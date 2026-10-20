<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Logo from '$lib/components/Logo.svelte';
	import { Button } from '$lib/ui/button';
	import { errorView } from './logic';

	const view = $derived(errorView(page.status, page.error, page.url.pathname));
</script>

<svelte:head><title>{view.title} · Kōri</title></svelte:head>

<!-- The own error page of tech.md §13.3 (kori-v4/screens/error.png): the name, what happened,
     and the way on: the portfolio for an unknown address, Повторить for a failed load. -->
<div class="flex min-h-svh flex-col">
	<header class="flex h-14 shrink-0 items-center border-b px-5">
		<a href={resolve('/')} class="w-max"><Logo /></a>
	</header>
	<main class="flex flex-1 flex-col items-start justify-center gap-5 px-4 py-16 md:px-18">
		<h1 class="mt-3 text-[28px]/8 md:text-quote">{view.title}</h1>
		<p class="max-w-[46ch] text-[14px]/[22px] text-muted-foreground">{view.text}</p>
		{#if view.request_id}
			<p class="text-caps text-grey-600">Код запроса {view.request_id}</p>
		{/if}
		{#if view.missing}
			<Button href={resolve('/portfolio')} class="mt-2 h-11 has-[>[data-slot=button-glyph]]:gap-3.5"
				><span data-slot="button-glyph" aria-hidden="true">→</span>Открыть портфель</Button
			>
		{:else}
			<Button variant="outline" class="mt-2 h-11 px-[18px]" onclick={() => invalidateAll()}
				>Повторить</Button
			>
		{/if}
	</main>
</div>
