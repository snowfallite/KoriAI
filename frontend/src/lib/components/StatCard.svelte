<script lang="ts">
	import * as Card from '$lib/ui/card';
	import { Skeleton } from '$lib/ui/skeleton';

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

	// The arrow glyph carries the direction, so the color is never the only cue.
	const TREND: Record<Trend, { glyph: string; said: string; class: string }> = {
		up: { glyph: '↑', said: 'рост', class: 'text-positive' },
		down: { glyph: '↓', said: 'падение', class: 'text-negative' },
		flat: { glyph: '→', said: 'без изменений', class: 'text-muted-foreground' }
	};
</script>

<Card.Root size="sm">
	<Card.Content class="space-y-1">
		<p class="tracking-wider text-muted-foreground uppercase">{label}</p>
		{#if loading}
			<Skeleton class="h-7 w-32" />
			<span class="sr-only">Загрузка</span>
		{:else}
			<p class="text-2xl">{value}</p>
			{#if delta}
				{@const trend = TREND[delta.trend]}
				<p class={trend.class}>
					<span aria-hidden="true">{trend.glyph}</span>
					<span class="sr-only">{trend.said}:</span>
					{delta.text}
				</p>
			{/if}
		{/if}
		{#if hint}
			<p class="text-muted-foreground">{hint}</p>
		{/if}
	</Card.Content>
</Card.Root>
