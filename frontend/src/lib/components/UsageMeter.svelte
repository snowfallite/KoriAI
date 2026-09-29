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

<div class="space-y-1.5 text-xs">
	<div class="flex items-baseline justify-between gap-2">
		<span>{label}</span>
		<span class={cn(ahead ? 'text-warning' : 'text-muted-foreground')}>
			{formatCompact(used)} / {formatCompact(quota)}{unit ? ` ${unit}` : ''}
		</span>
	</div>
	<div class="relative">
		<!-- Ink fill by default; the warning color once usage runs ahead of the pace. -->
		<Progress
			value={Math.min(share, 1) * 100}
			aria-label={label}
			class={cn(
				'h-1.5',
				ahead
					? '[&_[data-slot=progress-indicator]]:bg-warning'
					: '[&_[data-slot=progress-indicator]]:bg-foreground'
			)}
		/>
		{#if mark !== undefined}
			<span
				class="absolute -top-1 h-3.5 w-0.5 -translate-x-1/2 bg-primary"
				style="left: {mark * 100}%"
				aria-hidden="true"
			></span>
			<span class="sr-only"
				>Темп: {formatPercent(mark, { digits: 0 })} квоты к сегодняшнему дню</span
			>
		{/if}
	</div>
</div>
