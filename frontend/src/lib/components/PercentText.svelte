<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import { formatPercent } from '$lib/utils/format';

	let {
		value,
		signed = false,
		digits = 2,
		colorize = false
	}: {
		/** A share: 0.12 is 12 %. A DecimalStr from the API or a number. */
		value: string | number;
		signed?: boolean;
		digits?: number;
		colorize?: boolean;
	} = $props();

	// The sign of what the reader sees: a share that rounds to zero stays uncolored.
	const shown = $derived(Math.sign(Math.round(Number(value) * 100 * 10 ** digits)));
</script>

<span
	class={cn(
		'whitespace-nowrap',
		colorize && shown > 0 && 'text-positive',
		colorize && shown < 0 && 'text-negative'
	)}>{formatPercent(value, { signed, digits })}</span
>
