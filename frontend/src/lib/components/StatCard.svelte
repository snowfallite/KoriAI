<script lang="ts">
	import { Skeleton } from '$lib/ui/skeleton';
	import { cn } from '$lib/utils/cn';

	type Trend = 'up' | 'down' | 'flat';

	let {
		label,
		value,
		delta,
		hint,
		loading = false
	}: {
		label: string;
		value: string;
		delta?: { text: string; trend: Trend };
		hint?: string;
		loading?: boolean;
	} = $props();

	// The arrow glyph carries the direction, so the color is never the only cue: growth in the
	// ink color, a fall in red (tech.md §13.3).
	const TREND: Record<Trend, { glyph: string; said: string; class: string }> = {
		up: { glyph: '↑', said: 'рост', class: 'text-positive' },
		down: { glyph: '↓', said: 'падение', class: 'text-negative' },
		flat: { glyph: '→', said: 'без изменений', class: 'text-muted-foreground' }
	};
</script>

<!-- A summary holds on its number (kori-v3, Карточки): no frame, hairlines above and below, a
     vertical line between neighbours in a row. -->
<div class="min-w-0 border-y py-4 pr-4 not-first:border-l not-first:pl-4">
	<p class="text-caps text-grey-600">{label}</p>
	{#if loading}
		<Skeleton class="mt-2.5 h-[26px] w-32" />
		<span class="sr-only">Загрузка</span>
	{:else}
		<p class="mt-2.5 text-[22px]/[26px] whitespace-nowrap tabular-nums">{value}</p>
		{#if delta}
			{@const trend = TREND[delta.trend]}
			<p class={cn('mt-1.5 text-[12px]/4 tabular-nums', trend.class)}>
				<span aria-hidden="true">{trend.glyph}</span>
				<span class="sr-only">{trend.said}:</span>
				{delta.text}
			</p>
		{/if}
	{/if}
	{#if hint}
		<p class="mt-1.5 text-[12px]/4 text-muted-foreground">{hint}</p>
	{/if}
</div>
