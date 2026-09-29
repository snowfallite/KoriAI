<script lang="ts">
	import type { InstrumentBrief } from '$lib/types';
	import InstrumentLogo from './InstrumentLogo.svelte';

	let {
		instrument,
		showTicker = true,
		size = 'sm'
	}: { instrument: InstrumentBrief; showTicker?: boolean; size?: 'sm' | 'md' } = $props();
</script>

<span class="inline-flex min-w-0 items-center gap-2">
	<InstrumentLogo
		src={instrument.logo_url}
		name={instrument.name}
		color={instrument.brand_color}
		size={size === 'md' ? 32 : 20}
	/>
	<span class={size === 'md' ? 'min-w-0 text-sm' : 'min-w-0 text-xs'}>
		<span class="block truncate">{instrument.name}</span>
		{#if showTicker && size === 'md'}
			<span class="block text-xs text-muted-foreground">{instrument.ticker}</span>
		{/if}
	</span>
	{#if showTicker && size === 'sm'}
		<span class="text-xs text-muted-foreground">{instrument.ticker}</span>
	{/if}
</span>
