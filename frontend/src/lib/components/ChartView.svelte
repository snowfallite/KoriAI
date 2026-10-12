<script lang="ts" module>
	import type { ECharts } from 'echarts/core';

	type Core = typeof import('echarts/core');

	let echarts: Promise<Core> | undefined;

	/** ECharts arrives with the first chart, only the parts the eight canvas kinds use (tech.md §2). */
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

	// A plate row: 36 px high, the value column 190 px wide past a 16 px gap (kori-v3, Портфель).
	const ROW = 36;
	const ROW_GAP = 6;
	const VALUES = 190;
	const GAP = 16;
	// A label of 14 px JetBrains Mono: 0.6 em a character, 12 px of padding on each side.
	const fits = (label: string, width: number) => label.length * 8.4 + 24 <= width;
	// The ladder steps toward the ground (ladderOn): light greys at night, dark ones by day.
	const PLATE = [
		'bg-foreground',
		'bg-grey-600 dark:bg-grey-300',
		'bg-grey-400',
		'bg-grey-300 dark:bg-grey-600'
	];
</script>

<script lang="ts">
	import type { ChartSpec } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import { Skeleton } from '$lib/ui/skeleton';
	import * as Table from '$lib/ui/table';
	import {
		type ChartTheme,
		type PlateGroup,
		formatAxisValue,
		isCartesian,
		ladderOn,
		toEChartsOption,
		toPlates
	} from '$lib/utils/chart-option';
	import { cn } from '$lib/utils/cn';
	import { formatMoney, formatNumber, formatPercent } from '$lib/utils/format';

	let {
		spec,
		height = 320,
		class: className
	}: { spec: ChartSpec; height?: number; class?: string } = $props();

	let figure = $state<HTMLElement>();
	let node = $state<HTMLDivElement>();
	let chart = $state.raw<ECharts>();
	let theme = $state.raw<ChartTheme>();
	let showData = $state(false);
	let width = $state(0);
	const dataId = $props.id();

	const cartesian = $derived(isCartesian(spec));
	const groups = $derived(theme && !isCartesian(spec) ? toPlates(spec, theme) : []);
	const track = $derived(Math.max(width - VALUES - GAP, 0));

	/** The chart wears the design tokens of the theme in force (tech.md §13.3). */
	function readTheme(el: HTMLElement): ChartTheme {
		const css = getComputedStyle(el);
		const token = (name: string) => css.getPropertyValue(name).trim();
		const surface = token('--card');
		return {
			text: token('--foreground'),
			muted: token('--muted-foreground'),
			grid: token('--chart-grid'),
			surface,
			font: css.fontFamily,
			series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => token(`--chart-${i}`)),
			positive: token('--positive'),
			negative: token('--negative'),
			primary: token('--primary'),
			ladder: ladderOn(['--grey-300', '--grey-400', '--grey-600'].map(token), surface)
		};
	}

	// The tokens follow the theme class of <html>.
	$effect(() => {
		const el = figure;
		if (!el) return;
		theme = readTheme(el);
		const retheme = new MutationObserver(() => (theme = readTheme(el)));
		retheme.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => retheme.disconnect();
	});

	// ECharts follows the size of its box.
	$effect(() => {
		const el = node;
		if (!el) return;
		let instance: ECharts | undefined;
		let gone = false;
		const resize = new ResizeObserver(() => instance?.resize());
		void loadECharts().then((core) => {
			if (gone) return;
			instance = core.init(el);
			chart = instance;
			resize.observe(el);
		});
		return () => {
			gone = true;
			resize.disconnect();
			instance?.dispose();
			chart = undefined;
		};
	});

	$effect(() => {
		if (chart && theme && isCartesian(spec)) chart.setOption(toEChartsOption(spec, theme), true);
	});

	/** A share's value in the unit of the y axis; money in whole units, as on the portfolio. */
	function valueOf(value: number): string {
		return spec.y.format === 'money'
			? formatMoney(value, spec.y.unit ?? 'RUB', { digits: 0 })
			: formatAxisValue(value, spec.y);
	}

	const shareOf = (share: number) => formatPercent(share, { digits: 1 });

	/** The plates as a picture: the same rows the page shows, drawn on a canvas. */
	function drawPlates(plates: PlateGroup[], t: ChartTheme, box: number): string {
		const scale = 2;
		const pad = 16;
		const titled = plates.length > 1;
		const rows = plates.reduce((n, group) => n + group.plates.length + (titled ? 1 : 0), 0);
		const full = Math.max(box, 320);
		const tall = 2 * pad + 24 + Math.max(rows, 1) * (ROW + ROW_GAP);
		const lane = full - 2 * pad - VALUES - GAP;
		const canvas = document.createElement('canvas');
		canvas.width = full * scale;
		canvas.height = tall * scale;
		const ctx = canvas.getContext('2d');
		if (!ctx) return '';
		ctx.scale(scale, scale);
		ctx.fillStyle = t.surface;
		ctx.fillRect(0, 0, full, tall);
		ctx.textBaseline = 'middle';
		ctx.font = `11px ${t.font}`;
		ctx.fillStyle = t.text;
		ctx.fillText(spec.title.toUpperCase(), pad, pad + 6);
		ctx.font = `14px ${t.font}`;
		let y = pad + 24;
		const text = (value: string, x: number, color: string, align: CanvasTextAlign = 'left') => {
			ctx.textAlign = align;
			ctx.fillStyle = color;
			ctx.fillText(value, x, y + ROW / 2);
		};
		for (const group of plates) {
			if (titled) {
				text(group.name, pad, t.muted);
				y += ROW + ROW_GAP;
			}
			for (const plate of group.plates) {
				const span = Math.max(plate.share * lane, 1);
				ctx.fillStyle = plate.color;
				ctx.fillRect(pad, y, span, ROW);
				const inside = plate.lead && ctx.measureText(plate.label).width + 24 <= span;
				text(plate.label, inside ? pad + 12 : pad + span + 12, inside ? t.surface : t.text);
				text(valueOf(plate.value), full - pad - 72, t.muted, 'right');
				text(shareOf(plate.share), full - pad, t.text, 'right');
				y += ROW + ROW_GAP;
			}
		}
		return canvas.toDataURL('image/png');
	}

	function downloadPng() {
		if (!theme) return;
		const url = chart
			? chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: theme.surface })
			: drawPlates(groups, theme, width);
		if (!url) return;
		const link = document.createElement('a');
		link.href = url;
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

<!-- No frame and no fill (kori-v3): a caption over a hairline, then the marks. -->
<figure bind:this={figure} class={cn('min-w-0', className)}>
	<figcaption
		class="flex items-baseline justify-between gap-4 border-b pb-3 text-caption uppercase"
	>
		<p class="min-w-0">
			{spec.title}{#if spec.subtitle}<span class="text-muted-foreground"
					>&nbsp;&nbsp;{spec.subtitle}</span
				>{/if}
		</p>
		<div class="flex shrink-0 gap-4">
			<Button
				variant="link"
				class="text-caption"
				disabled={cartesian ? !chart : !groups.length}
				onclick={downloadPng}
			>
				PNG
			</Button>
			<Button
				variant="link"
				class="text-caption"
				aria-expanded={showData}
				aria-controls={dataId}
				onclick={() => (showData = !showData)}
			>
				Данные
			</Button>
		</div>
	</figcaption>
	{#if cartesian}
		<div class="relative mt-4" style="height: {height}px">
			<div bind:this={node} class="size-full" role="img" aria-label={spec.title}></div>
			{#if !chart}
				<Skeleton class="absolute inset-0" />
			{/if}
		</div>
	{:else}
		<!-- A pie as plates: the largest share in the ink color, the rest down the grey ladder. -->
		<div
			bind:clientWidth={width}
			role="img"
			aria-label={spec.title}
			class="space-y-4 pt-4 text-ui tabular-nums"
		>
			{#each groups as group, g (g)}
				<div class="space-y-1.5">
					{#if groups.length > 1}
						<p class="text-caption text-muted-foreground uppercase">{group.name}</p>
					{/if}
					{#each group.plates as plate, i (i)}
						{@const inside = plate.lead && fits(plate.label, plate.share * track)}
						<div class="grid grid-cols-[minmax(0,1fr)_190px] items-center gap-x-4">
							<div class="flex h-9 min-w-0 items-center">
								<span
									class={cn(
										'flex h-9 shrink-0 items-center',
										PLATE[Math.min(plate.rank, PLATE.length - 1)]
									)}
									style="width: {plate.share * 100}%"
								>
									{#if inside}
										<span class="truncate px-3 text-[14px] text-background">{plate.label}</span>
									{/if}
								</span>
								{#if !inside}
									<span class="ml-3 truncate text-[14px] text-prose">{plate.label}</span>
								{/if}
							</div>
							<span class="text-right whitespace-nowrap text-muted-foreground"
								>{valueOf(plate.value)}<span class="inline-block w-16 text-foreground"
									>{shareOf(plate.share)}</span
								></span
							>
						</div>
					{/each}
				</div>
			{:else}
				{#if theme}
					<p class="text-muted-foreground">Нет данных</p>
				{/if}
			{/each}
		</div>
	{/if}
	<div id={dataId} hidden={!showData} class="mt-4 max-h-72 overflow-auto">
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
