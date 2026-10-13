<script lang="ts">
	import { Button } from '$lib/ui/button';
	import { formatMoney, formatPercent } from '$lib/utils/format';
	import { askHref, hero, PORTFOLIO_QUESTION, type Summary } from '../logic';

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
	// Growth in the ink color, a fall in red, always with its arrow and sign (tech.md §13.3).
	const TREND = {
		up: { glyph: '↑', class: 'text-positive' },
		down: { glyph: '↓', class: 'text-negative' },
		flat: { glyph: '', class: '' }
	};
	const trend = $derived(TREND[summary.trend]);
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- askHref gives the chat path with its query -->
<!-- One big number a screen (kori-v3, Портфель): the total, the result from the purchase prices,
     and the way to ask about it. -->
<section
	aria-label="Итоги"
	class="flex flex-wrap items-end justify-between gap-8 border-b px-4 pt-10 pb-10 md:px-12 md:pt-16 md:pb-14"
>
	<div class="min-w-0">
		<p class="text-caps tracking-[0.04em] text-grey-600 uppercase">{label}</p>
		<p
			class="mt-[18px] text-[48px]/[52px] tracking-[-0.03em] whitespace-nowrap tabular-nums md:text-hero"
		>
			{total.number}<span class="ml-4 text-[24px] tracking-normal text-grey-600 md:text-[44px]"
				>{total.unit}</span
			>
		</p>
		<p class="mt-[22px] flex flex-wrap items-baseline gap-x-5 gap-y-2 text-lead tabular-nums">
			{#if summary.yield !== null}
				<span class={trend.class}>
					{#if trend.glyph}<span aria-hidden="true">{trend.glyph}</span>{/if}
					{formatMoney(summary.yield, summary.total.currency, { signed: true, digits: 0 })}
				</span>
			{/if}
			{#if summary.yieldShare !== null}
				<span class={trend.class}>
					{formatPercent(summary.yieldShare, { signed: true })}
				</span>
			{/if}
			<span class="text-caps tracking-[0.04em] text-grey-600 uppercase">
				{summary.yield === null ? caption : `от средней цены покупки · ${caption}`}
			</span>
		</p>
	</div>
	<Button variant="ai" size="lg" href={askHref(PORTFOLIO_QUESTION)}>
		<span data-slot="button-glyph" aria-hidden="true">→</span>Спросить Kōri о портфеле
	</Button>
</section>
