<script lang="ts">
	import { Button } from '$lib/ui/button';
	import { cn } from '$lib/utils/cn';
	import { askHref, hero, PORTFOLIO_QUESTION, type Summary, yieldText } from '../logic';

	let {
		label,
		summary,
		caption
	}: {
		label: string;
		summary: Summary;
		/** What the total covers: «29 позиций на 2 счетах». */
		caption: string;
	} = $props();

	const total = $derived(hero(summary.total));
	const result = $derived(yieldText(summary));
	// Growth in the ink color, a fall in red; the total is the one value that wears an arrow
	// (tech.md §13.3).
	const TREND = {
		up: { glyph: '↑', class: 'text-positive' },
		down: { glyph: '↓', class: 'text-negative' },
		flat: { glyph: '', class: '' }
	};
	const trend = $derived(TREND[summary.trend]);
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- askHref gives the chat path with its query -->
<!-- One big number a screen (kori-v4, Портфель): the total, the result to the average purchase
     price and what the total covers on lines of their own, and the way to ask about it. -->
<section
	aria-label="Итоги"
	class="flex flex-wrap items-end justify-between gap-8 border-b px-4 pt-10 pb-10 md:px-12 md:pt-16 md:pb-14"
>
	<div class="min-w-0">
		<p class="text-caps text-grey-600">{label}</p>
		<p
			class="mt-[18px] text-[48px]/[52px] tracking-[-0.03em] whitespace-nowrap tabular-nums md:text-hero"
		>
			{total.number}<span class="ml-4 text-[24px] tracking-normal text-grey-600 md:text-[44px]"
				>{total.unit}</span
			>
		</p>
		{#if result}
			<p class="mt-[22px] flex flex-wrap items-baseline gap-x-3.5 gap-y-2 text-lead tabular-nums">
				<span class={trend.class}
					>{#if trend.glyph}<span aria-hidden="true">{trend.glyph}</span>&nbsp;{/if}{result}</span
				>
				<span class="text-ui text-grey-600">к средней цене покупки</span>
			</p>
		{/if}
		<p class={cn('text-ui text-grey-600', result ? 'mt-2' : 'mt-[22px]')}>{caption}</p>
	</div>
	<Button
		variant="ai"
		size="lg"
		href={askHref(PORTFOLIO_QUESTION)}
		class="has-[>[data-slot=button-glyph]]:gap-3.5 has-[>[data-slot=button-glyph]]:pr-9"
	>
		<span data-slot="button-glyph" aria-hidden="true">→</span>Спросить о портфеле
	</Button>
</section>
