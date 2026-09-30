import type {
	CustomSeriesOption,
	CustomSeriesRenderItem,
	EChartsOption,
	PieSeriesOption,
	SeriesOption,
	XAXisComponentOption,
	YAXisComponentOption
} from 'echarts';
import type { ChartSpec } from '$lib/types';
import {
	formatCompact,
	formatDate,
	formatMoney,
	formatMonth,
	formatNumber,
	formatPercent,
	formatQuarter,
	formatYear
} from './format';

type Axis = ChartSpec['x'];
type Series = ChartSpec['series'][number];
type Point = Series['points'][number];

/** Colors and font of a chart, read from the design tokens (tech.md §13.3). */
export interface ChartTheme {
	text: string;
	muted: string;
	grid: string;
	surface: string;
	font: string;
	/** --chart-1 … --chart-8, in slot order. */
	series: string[];
	positive: string;
	negative: string;
}

// These kinds place marks by category whatever the spec says about the x axis.
const BY_CATEGORY = new Set<ChartSpec['kind']>(['candlestick', 'heatmap', 'waterfall']);
const BAR_MAX_WIDTH = 24;

/** An axis value as people read it; percent axes carry shares (0.12 is 12 %), as PercentText. */
export function formatAxisValue(value: unknown, axis: Axis): string {
	if (typeof value !== 'number' && typeof value !== 'string') return '';
	const text = (() => {
		switch (axis.format) {
			case 'date':
				return formatDate(value);
			case 'month':
				return formatMonth(value);
			case 'quarter':
				return formatQuarter(value);
			case 'year':
				return formatYear(value);
			case 'money':
				return formatMoney(value, axis.unit ?? 'RUB', { compact: true });
			case 'percent':
				return formatPercent(value, { digits: 1 });
			case 'compact':
				return formatCompact(value);
			case 'number':
				return formatNumber(value);
			default:
				if (axis.type === 'time') return formatDate(value);
				return typeof value === 'number' ? formatNumber(value) : value;
		}
	})();
	// A category the format cannot read keeps its own name.
	return text === '—' ? String(value) : text;
}

/** Categorical slots go in order to series without a role; roles keep fixed colors. */
function paint(series: Series[], theme: ChartTheme): { color: string; cycled: boolean }[] {
	let slot = 0;
	return series.map(({ role }) => {
		if (role === 'positive') return { color: theme.positive, cycled: false };
		if (role === 'negative') return { color: theme.negative, cycled: false };
		if (role === 'neutral') return { color: theme.muted, cycled: false };
		if (role === 'benchmark') return { color: theme.text, cycled: false };
		const n = slot++;
		const color = theme.series[n % theme.series.length] ?? theme.text;
		// Past the eighth slot a color repeats; a dashed line keeps the series apart.
		return { color, cycled: n >= theme.series.length };
	});
}

function unique(values: string[]): string[] {
	return [...new Set(values)];
}

function finite(values: (number | null)[]): number[] {
	return values.filter((v): v is number => v !== null && Number.isFinite(v));
}

export function toEChartsOption(spec: ChartSpec, theme: ChartTheme): EChartsOption {
	const colors = paint(spec.series, theme);
	const legend = spec.series.length > 1 && spec.kind !== 'pie';
	const item = spec.kind === 'pie' || spec.kind === 'scatter' || spec.kind === 'heatmap';
	const base: EChartsOption = {
		backgroundColor: 'transparent',
		// Ticks at UTC midnight fall on the same day in Moscow (UTC+3).
		useUTC: true,
		animationDuration: 300,
		color: theme.series,
		textStyle: { fontFamily: theme.font, color: theme.muted },
		legend: { show: legend, type: 'scroll', top: 0, left: 0, textStyle: { color: theme.text } },
		tooltip: {
			trigger: item ? 'item' : 'axis',
			backgroundColor: theme.surface,
			borderColor: theme.grid,
			textStyle: { color: theme.text, fontFamily: theme.font }
		}
	};

	if (spec.kind === 'pie') return { ...base, series: pies(spec, theme) };

	const categories = BY_CATEGORY.has(spec.kind) || spec.x.type === 'category';
	const xs = unique(spec.series.flatMap((s) => s.points.map((p) => String(p.x))));
	const xAxis: XAXisComponentOption = {
		type: categories ? 'category' : spec.x.type,
		...(categories ? { data: xs } : {}),
		name: spec.x.label ?? undefined,
		nameLocation: 'middle',
		nameGap: 28,
		axisLabel: {
			color: theme.muted,
			formatter: (value: string | number) => formatAxisValue(value, spec.x)
		},
		axisPointer: { label: { formatter: ({ value }) => formatAxisValue(value, spec.x) } },
		axisLine: { lineStyle: { color: theme.grid } },
		axisTick: { show: false },
		splitLine: { show: false }
	};
	const yAxes = [spec.y, ...(spec.y2 ? [spec.y2] : [])].map((axis): YAXisComponentOption => ({
		type: axis.type === 'log' ? 'log' : 'value',
		name: axis.label ?? undefined,
		axisLabel: { color: theme.muted, formatter: (value: number) => formatAxisValue(value, axis) },
		splitLine: { lineStyle: { color: theme.grid } }
	}));
	const grid = {
		left: 8,
		right: 16,
		top: legend ? 36 : 12,
		bottom: spec.kind === 'heatmap' ? 48 : 8,
		outerBoundsMode: 'same' as const,
		outerBoundsContain: 'all' as const
	};

	if (spec.kind === 'heatmap') return { ...base, ...heatmap(spec, theme, xs, xAxis), grid };

	const series = spec.series.map((s, i): SeriesOption => {
		const yAxisIndex = s.axis === 'y2' && spec.y2 ? 1 : 0;
		const axis = yAxisIndex === 1 && spec.y2 ? spec.y2 : spec.y;
		const common = {
			name: s.name,
			color: colors[i]?.color,
			yAxisIndex,
			tooltip: { valueFormatter: (value: unknown) => formatAxisValue(value, axis) }
		};
		const pairs = s.points.map((p) => [p.x, p.y]);
		switch (spec.kind) {
			case 'bar':
			case 'stacked_bar':
				return {
					...common,
					type: 'bar',
					data: pairs,
					barMaxWidth: BAR_MAX_WIDTH,
					// Stacked segments part with a surface gap, not a stroke.
					...(spec.kind === 'stacked_bar'
						? { stack: 'total', itemStyle: { borderColor: theme.surface, borderWidth: 1 } }
						: {})
				};
			case 'scatter':
				return {
					...common,
					type: 'scatter',
					data: pairs,
					symbolSize: 8,
					itemStyle: { borderColor: theme.surface, borderWidth: 1 }
				};
			case 'candlestick':
				return {
					...common,
					type: 'candlestick',
					data: s.points.map((p) => [String(p.x), p.o, p.c, p.l, p.h]),
					encode: { x: 0, y: [1, 2, 3, 4] },
					barMaxWidth: BAR_MAX_WIDTH,
					// A hollow rise and a filled fall read apart without color too.
					itemStyle: {
						color: theme.surface,
						color0: theme.negative,
						borderColor: theme.positive,
						borderColor0: theme.negative
					}
				};
			case 'waterfall':
				return waterfall(s.points, xs, theme, common);
			default:
				return {
					...common,
					type: 'line',
					data: pairs,
					showSymbol: false,
					symbolSize: 8,
					lineStyle: {
						width: 2,
						type: s.role === 'benchmark' || colors[i]?.cycled ? 'dashed' : 'solid'
					},
					...(spec.kind === 'area' ? { areaStyle: { opacity: 0.1 } } : {})
				};
		}
	});
	return { ...base, grid, xAxis, yAxis: yAxes, series };
}

function pies(spec: ChartSpec, theme: ChartTheme): PieSeriesOption[] {
	const n = spec.series.length;
	return spec.series.map((s, i) => ({
		type: 'pie',
		name: s.name,
		radius: ['45%', `${Math.min(70, 140 / n)}%`],
		center: [`${((i + 0.5) / n) * 100}%`, '50%'],
		data: s.points.map((p) => ({ name: String(p.x), value: p.y ?? 0 })),
		label: {
			color: theme.text,
			formatter: ({ name, percent }: { name: string; percent?: number }) =>
				`${name}\n${formatPercent((percent ?? 0) / 100, { digits: 1 })}`
		},
		itemStyle: { borderColor: theme.surface, borderWidth: 2 },
		tooltip: { valueFormatter: (value: unknown) => formatAxisValue(value, spec.y) }
	}));
}

function heatmap(
	spec: ChartSpec,
	theme: ChartTheme,
	xs: string[],
	xAxis: XAXisComponentOption
): EChartsOption {
	const points = spec.series.flatMap((s) => s.points);
	const ys = unique(points.map((p) => p.y_cat ?? ''));
	const zs = finite(points.map((p) => p.z));
	const [low, high] = zs.length ? [Math.min(...zs), Math.max(...zs)] : [0, 1];
	// Values on both sides of zero diverge from a gray midpoint; the rest run on one hue.
	const diverging = low < 0 && high > 0;
	const bound = Math.max(Math.abs(low), Math.abs(high));
	const [min, max] = diverging ? [-bound, bound] : [low, high > low ? high : low + 1];
	const cells = xs.length * ys.length;
	return {
		xAxis,
		yAxis: {
			type: 'category',
			data: ys,
			axisLabel: { color: theme.muted },
			axisLine: { lineStyle: { color: theme.grid } },
			axisTick: { show: false }
		},
		visualMap: {
			type: 'continuous',
			min,
			max,
			orient: 'horizontal',
			left: 'center',
			bottom: 0,
			itemHeight: 160,
			itemWidth: 10,
			textStyle: { color: theme.muted },
			formatter: (value: unknown) => formatNumber(value as number, 2),
			inRange: {
				color: diverging
					? [theme.negative, theme.grid, theme.series[0] ?? theme.text]
					: [theme.grid, theme.series[0] ?? theme.text]
			}
		},
		series: spec.series.map((s) => ({
			type: 'heatmap',
			name: s.name,
			data: s.points.map((p) => [xs.indexOf(String(p.x)), ys.indexOf(p.y_cat ?? ''), p.z]),
			// Values in the cells only while they stay readable.
			label: {
				show: cells <= 36,
				color: theme.text,
				textBorderColor: theme.surface,
				textBorderWidth: 2,
				formatter: ({ value }: { value: unknown }) =>
					formatNumber((value as (number | null)[])[2] ?? Number.NaN, 2)
			},
			itemStyle: { borderColor: theme.surface, borderWidth: 2 }
		}))
	};
}

/** Each step floats from the running total before it to the total after it. */
function waterfall(
	points: Point[],
	xs: string[],
	theme: ChartTheme,
	common: CustomSeriesOption
): CustomSeriesOption {
	let total = 0;
	const data = points.map((p) => {
		const delta = p.y ?? 0;
		const step = [xs.indexOf(String(p.x)), total, total + delta, delta];
		total += delta;
		return step;
	});
	const renderItem: CustomSeriesRenderItem = (_, api) => {
		const x = api.value(0);
		const [x0 = 0, y0 = 0] = api.coord([x, api.value(1)]);
		const [, y1 = 0] = api.coord([x, api.value(2)]);
		const band = (api.size?.([1, 0]) as number[] | undefined)?.[0] ?? 0;
		const width = Math.min(BAR_MAX_WIDTH, band * 0.6);
		return {
			type: 'rect',
			shape: { x: x0 - width / 2, y: Math.min(y0, y1), width, height: Math.abs(y1 - y0) },
			style: { fill: Number(api.value(3)) >= 0 ? theme.positive : theme.negative }
		};
	};
	return { ...common, type: 'custom', data, renderItem, encode: { x: 0, y: [1, 2], tooltip: [3] } };
}
