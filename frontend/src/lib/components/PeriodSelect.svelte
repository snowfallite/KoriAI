<script lang="ts">
	import type { PeriodCode } from '$lib/types';
	import * as ToggleGroup from '$lib/ui/toggle-group';

	const LABEL: Record<PeriodCode, string> = {
		'1m': '1 мес',
		'3m': '3 мес',
		'6m': '6 мес',
		ytd: 'с нач. года',
		'1y': '1 год',
		'3y': '3 года',
		'5y': '5 лет',
		max: 'всё'
	};

	let {
		value,
		options = Object.keys(LABEL) as PeriodCode[],
		onChange
	}: {
		value: PeriodCode;
		options?: PeriodCode[];
		onChange: (period: PeriodCode) => void;
	} = $props();
</script>

<!-- A period is always chosen: a click on the pressed one keeps it. -->
<ToggleGroup.Root
	type="single"
	variant="outline"
	size="sm"
	aria-label="Период"
	bind:value={() => value, (next) => next && onChange(next as PeriodCode)}
>
	{#each options as period (period)}
		<ToggleGroup.Item value={period}>{LABEL[period]}</ToggleGroup.Item>
	{/each}
</ToggleGroup.Root>
