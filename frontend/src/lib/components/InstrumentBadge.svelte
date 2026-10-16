<script lang="ts">
	import type { InstrumentBrief } from '$lib/types';
	import InstrumentLogo from './InstrumentLogo.svelte';

	let {
		instrument,
		showTicker = true,
		size = 'sm'
	}: { instrument: InstrumentBrief; showTicker?: boolean; size?: 'sm' | 'md' } = $props();
</script>

<!-- The tile, the name and the ticker in a grey caption (kori-v3, Портфель). -->
{#if size === 'md'}
	<span class="inline-flex min-w-0 items-center gap-3">
		<InstrumentLogo src={instrument.logo_url} name={instrument.name} size={32} />
		<span class="flex min-w-0 flex-col">
			<span class="truncate text-[14px]/4">{instrument.name}</span>
			{#if showTicker}
				<span class="text-caption text-grey-600">{instrument.ticker}</span>
			{/if}
		</span>
	</span>
{:else}
	<span class="inline-flex min-w-0 items-center gap-2">
		<InstrumentLogo src={instrument.logo_url} name={instrument.name} size={20} />
		<span class="truncate text-ui">{instrument.name}</span>
		{#if showTicker}
			<span class="text-caption text-grey-600">{instrument.ticker}</span>
		{/if}
	</span>
{/if}
