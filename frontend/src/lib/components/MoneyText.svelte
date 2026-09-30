<script lang="ts">
	import type { Money } from '$lib/types';
	import { cn } from '$lib/utils/cn';
	import { formatMoney } from '$lib/utils/format';

	let {
		money,
		signed = false,
		compact = false,
		colorize = false
	}: { money: Money; signed?: boolean; compact?: boolean; colorize?: boolean } = $props();

	// The sign of what the reader sees: an amount that rounds to zero kopecks stays uncolored.
	const shown = $derived(Math.sign(Math.round(Number(money.amount) * 100)));
</script>

<span
	class={cn(
		'whitespace-nowrap',
		colorize && shown > 0 && 'text-positive',
		colorize && shown < 0 && 'text-negative'
	)}>{formatMoney(money.amount, money.currency, { signed, compact })}</span
>
