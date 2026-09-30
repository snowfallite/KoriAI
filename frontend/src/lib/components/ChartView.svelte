<script lang="ts" module>
	import type { ECharts } from 'echarts/core';

	type Core = typeof import('echarts/core');

	let echarts: Promise<Core> | undefined;

	/** ECharts arrives with the first chart, only the parts the nine kinds use (tech.md §2). */
	function loadECharts(): Promise<Core> {
		echarts ??= Promise.all([
			import('echarts/core'),
			import('echarts/charts'),
			import('echarts/components'),
			import('echarts/renderers')
		]).then(([core, charts, components, renderers]) => {
			core.use([
				charts.LineChart,
				charts.BarChart,
				charts.PieChart,
				charts.CandlestickChart,
				charts.ScatterChart,
				charts.HeatmapChart,
				charts.CustomChart,
				components.GridComponent,
				components.TooltipComponent,
				components.AxisPointerComponent,
				components.LegendComponent,
				components.VisualMapContinuousComponent,
				renderers.CanvasRenderer
			]);
			return core;
		});
		return echarts;
	}
</script>

<script lang="ts">
	import Download from '@lucide/svelte/icons/download';
	import Table2 from '@lucide/svelte/icons/table-2';
	import type { ChartSpec } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import { Skeleton } from '$lib/ui/skeleton';
	import * as Table from '$lib/ui/table';
	import { type ChartTheme, formatAxisValue, toEChartsOption } from '$lib/utils/chart-option';
	import { cn } from '$lib/utils/cn';
	import { formatNumber } from '$lib/utils/format';

	let {
		spec,
		height = 320,
		class: className
	}: { spec: ChartSpec; height?: number; class?: string } = $props();

	let node = $state<HTMLDivElement>();
	let chart = $state.raw<ECharts>();
	let theme = $state.raw<ChartTheme>();
	let showData = $state(false);
	const dataId = $props.id();

	/** The chart wears the design tokens of the theme in force (tech.md §13.3). */
	function readTheme(el: HTMLElement): ChartTheme {
		const css = getComputedStyle(el);
		const token = (name: string) => css.getPropertyValue(name).trim();
		return {
			text: token('--foreground'),
			muted: token('--muted-foreground'),
			grid: token('--chart-grid'),
			surface: token('--card'),
			font: css.fontFamily,
			series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => token(`--chart-${i}`)),
			positive: token('--positive'),
			negative: token('--negative')
		};
	}

	// ECharts follows the DOM: the size of its box and the theme class of <html>.
	$effect(() => {
		const el = node;
		if (!el) return;
		let instance: ECharts | undefined;
		let gone = false;
		const resize = new ResizeObserver(() => instance?.resize());
		const retheme = new MutationObserver(() => (theme = readTheme(el)));
		theme = readTheme(el);
		void loadECharts().then((core) => {
			if (gone) return;
			instance = core.init(el);
			chart = instance;
			resize.observe(el);
			retheme.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		});
		return () => {
			gone = true;
			resize.disconnect();
			retheme.disconnect();
			instance?.dispose();
			chart = undefined;
		};
	});

	$effect(() => {
		if (chart && theme) chart.setOption(toEChartsOption(spec, theme), true);
	});

	function downloadPng() {
		if (!chart || !theme) return;
		const link = document.createElement('a');
		link.href = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: theme.surface });
		link.download = `${spec.title || 'график'}.png`;
		link.click();
	}

	// The data view: every point in a table, the same values the chart shows.
	const columns = $derived(
		spec.kind === 'candlestick'
			? ['Серия', spec.x.label ?? 'Дата', 'Открытие', 'Максимум', 'Минимум', 'Закрытие']
			: spec.kind === 'heatmap'
				? ['Серия', spec.x.label ?? 'Столбец', spec.y.label ?? 'Строка', 'Значение']
				: ['Серия', spec.x.label ?? 'X', spec.y.label ?? 'Значение']
	);
	const rows = $derived(
		spec.series.flatMap((s) => {
			const axis = s.axis === 'y2' && spec.y2 ? spec.y2 : spec.y;
			return s.points.map((p) => {
				const x = formatAxisValue(p.x, spec.x);
				if (spec.kind === 'candlestick')
					return [s.name, x, ...[p.o, p.h, p.l, p.c].map((v) => formatAxisValue(v, axis))];
				if (spec.kind === 'heatmap') return [s.name, x, p.y_cat ?? '', formatNumber(p.z ?? '', 2)];
				return [s.name, x, formatAxisValue(p.y, axis)];
			});
		})
	);
</script>

<figure class={cn('space-y-2 bg-card p-3 ring-1 ring-foreground/10', className)}>
	<figcaption class="flex items-start justify-between gap-2">
		<div class="min-w-0">
			<p class="text-sm font-medium">{spec.title}</p>
			{#if spec.subtitle}
				<p class="text-xs text-muted-foreground">{spec.subtitle}</p>
			{/if}
		</div>
		<div class="flex shrink-0 gap-1">
			<Button variant="ghost" size="sm" disabled={!chart} onclick={downloadPng}>
				<Download />
				PNG
			</Button>
			<Button
				variant="ghost"
				size="sm"
				aria-expanded={showData}
				aria-controls={dataId}
				onclick={() => (showData = !showData)}
			>
				<Table2 />
				Данные
			</Button>
		</div>
	</figcaption>
	<div class="relative" style="height: {height}px">
		<div bind:this={node} class="size-full" role="img" aria-label={spec.title}></div>
		{#if !chart}
			<Skeleton class="absolute inset-0" />
		{/if}
	</div>
	<div id={dataId} hidden={!showData} class="max-h-72 overflow-auto">
		{#if showData}
			<Table.Root>
				<Table.Header>
					<Table.Row>
						{#each columns as column, i (i)}
							<Table.Head>{column}</Table.Head>
						{/each}
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each rows as row, i (i)}
						<Table.Row>
							{#each row as cell, j (j)}
								<Table.Cell>{cell}</Table.Cell>
							{/each}
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		{/if}
	</div>
</figure>
