<script lang="ts">
	import { Progress } from '$lib/ui/progress';
	import { cn } from '$lib/utils/cn';
	import { formatCompact, formatPercent } from '$lib/utils/format';

	let {
		label,
		used,
		quota,
		pace,
		unit
	}: {
		label: string;
		used: number;
		quota: number;
		/** The share of the quota the pace allows by today (0..1): the mark on the bar. */
		pace?: number;
		unit?: string;
	} = $props();

	const share = $derived(quota > 0 ? used / quota : 0);
	const mark = $derived(pace === undefined ? undefined : Math.min(Math.max(pace, 0), 1));
	const ahead = $derived(mark !== undefined && share > mark);
</script>

<!-- A row of the usage sheet (kori-v3, Карточки): the family in caps, a 6 px bar with the red mark
     of the pace, «6,1 млн из 250 млн» on the right. Usage ahead of the pace turns to warning. -->
<div
	class="grid grid-cols-[52px_minmax(0,1fr)_minmax(164px,max-content)] items-center gap-x-4 text-ui tabular-nums"
>
	<span class="truncate text-caption uppercase">{label}</span>
	<div class="relative">
		<Progress
			value={Math.min(share, 1) * 100}
			aria-label={label}
			class={cn('h-1.5', ahead && '[&_[data-slot=progress-indicator]]:bg-warning')}
		/>
		{#if mark !== undefined}
			<span
				class="absolute -top-[5px] h-4 w-0.5 -translate-x-1/2 bg-primary"
				style="left: {mark * 100}%"
				aria-hidden="true"
			></span>
			<span class="sr-only"
				>Темп: {formatPercent(mark, { digits: 0 })} квоты к сегодняшнему дню</span
			>
		{/if}
	</div>
	<span class="text-right text-muted-foreground">
		<span class={ahead ? 'text-warning' : 'text-foreground'}>{formatCompact(used)}</span>
		из {formatCompact(quota)}{unit ? ` ${unit}` : ''}
	</span>
</div>
