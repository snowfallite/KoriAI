import type {
	CustomSeriesOption,
	CustomSeriesRenderItem,
	EChartsOption,
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
	/** --primary: the red end of a correlation. */
	primary: string;
	/** The grey ladder under the ink, from the boldest on this ground to the faintest. */
	ladder: string[];
}

/** Every kind but the pie draws on the ECharts canvas; a pie draws as plates (toPlates). */
export type CartesianSpec = ChartSpec & { kind: Exclude<ChartSpec['kind'], 'pie'> };

export function isCartesian(spec: ChartSpec): spec is CartesianSpec {
	return spec.kind !== 'pie';
}

// These kinds place marks by category whatever the spec says about the x axis.
const BY_CATEGORY = new Set<ChartSpec['kind']>(['candlestick', 'heatmap', 'waterfall']);
const BAR_MAX_WIDTH = 24;
const FROM_ZERO = new Set<ChartSpec['kind']>(['bar', 'stacked_bar', 'waterfall']);
// The benchmark dash of v3: 4 px of line, 4 px of gap.
const DASH = [4, 4];

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

/** WCAG relative luminance of a #rgb or #rrggbb color; null for any other notation. */
function luminance(color: string): number | null {
	const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color.trim())?.[1];
	if (!hex) return null;
	const full = hex.length === 3 ? [...hex].map((digit) => digit + digit).join('') : hex;
	const channel = (at: number) => {
		const c = parseInt(full.slice(at, at + 2), 16) / 255;
		return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	};
	return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
}

function contrast(a: string, b: string): number {
	const [la, lb] = [luminance(a), luminance(b)];
	if (la === null || lb === null) return 1;
	return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** The greys from the one that stands out most on the ground to the faintest: light first at
 * night, dark first by day. Colors it cannot read keep their order. */
export function ladderOn(greys: string[], ground: string): string[] {
	return greys
		.map((grey, i) => ({ grey, i, contrast: contrast(grey, ground) }))
		.sort((a, b) => b.contrast - a.contrast || a.i - b.i)
		.map(({ grey }) => grey);
}

/** Categorical slots go in order to series without a role; roles keep fixed colors. */
function paint(series: Series[], theme: ChartTheme): { color: string; cycled: boolean }[] {
	let slot = 0;
	return series.map(({ role }) => {
		if (role === 'positive') return { color: theme.positive, cycled: false };
		if (role === 'negative') return { color: theme.negative, cycled: false };
		// A benchmark and a neutral series step back into grey; the benchmark also dashes.
		if (role === 'neutral' || role === 'benchmark') return { color: theme.muted, cycled: false };
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

export function toEChartsOption(spec: CartesianSpec, theme: ChartTheme): EChartsOption {
	const colors = paint(spec.series, theme);
	const legend = spec.series.length > 1;
	const item = spec.kind === 'scatter' || spec.kind === 'heatmap';
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
			// Full dates are long: a label that would overlap its neighbour stays hidden.
			hideOverlap: true,
			formatter: (value: string | number) => formatAxisValue(value, spec.x)
		},
		axisPointer: { label: { formatter: ({ value }) => formatAxisValue(value, spec.x) } },
		axisLine: { lineStyle: { color: theme.grid } },
		axisTick: { show: false },
		splitLine: { show: false }
	};
	const yAxes = [spec.y, ...(spec.y2 ? [spec.y2] : [])].map((axis): YAXisComponentOption => ({
		type: axis.type === 'log' ? 'log' : 'value',
		// Bars grow from zero; prices and lines fit their own range.
		scale: !FROM_ZERO.has(spec.kind),
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

	// ECharts reads a bare date as local midnight, a day early east of Moscow; Date.parse
	// puts it at UTC midnight, where the UTC ticks and the Moscow labels agree.
	const time = xAxis.type === 'time';
	const at = (x: Point['x']) => (time && typeof x === 'string' ? Date.parse(x) : x);

	const series = spec.series.map((s, i): SeriesOption => {
		const yAxisIndex = s.axis === 'y2' && spec.y2 ? 1 : 0;
		const axis = yAxisIndex === 1 && spec.y2 ? spec.y2 : spec.y;
		const common = {
			name: s.name,
			color: colors[i]?.color,
			yAxisIndex,
			tooltip: { valueFormatter: (value: unknown) => formatAxisValue(value, axis) }
		};
		const pairs = s.points.map((p) => [at(p.x), p.y]);
		switch (spec.kind) {
			case 'bar':
			case 'stacked_bar':
				return {
					...common,
					type: 'bar',
					// A loss is red in any series: a bar below zero wears the negative color.
					data: pairs.map((pair, j) =>
						(s.points[j]?.y ?? 0) < 0 ? { value: pair, itemStyle: { color: theme.negative } } : pair
					),
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
					// A hollow rise and a filled red fall read apart without color too.
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
					lineStyle:
						s.role === 'benchmark'
							? { width: 1.25, type: DASH }
							: { width: 2, type: colors[i]?.cycled ? 'dashed' : 'solid' },
					// A benchmark stays a dashed line over the wash of the series it measures.
					...(spec.kind === 'area' && s.role !== 'benchmark' ? { areaStyle: { opacity: 0.1 } } : {})
				};
		}
	});
	return { ...base, grid, xAxis, yAxis: yAxes, series };
}

function heatmap(
	spec: CartesianSpec,
	theme: ChartTheme,
	xs: string[],
	xAxis: XAXisComponentOption
): EChartsOption {
	const points = spec.series.flatMap((s) => s.points);
	const ys = unique(points.map((p) => p.y_cat ?? ''));
	const zs = finite(points.map((p) => p.z));
	// Zero is the ground: grey below it, red above it. Correlations keep the whole −1…+1 scale;
	// larger values stretch it evenly on both sides.
	const bound = zs.reduce((most, z) => Math.max(most, Math.abs(z)), 1);
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
			min: -bound,
			max: bound,
			orient: 'horizontal',
			left: 'center',
			bottom: 0,
			itemHeight: 160,
			itemWidth: 10,
			textStyle: { color: theme.muted },
			formatter: (value: unknown) => formatNumber(value as number, 2),
			inRange: { color: [theme.ladder.at(-1) ?? theme.muted, theme.surface, theme.primary] }
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

/** One share of a pie drawn as a plate. */
interface Plate {
	label: string;
	value: number;
	/** The part of the series total, in (0, 1]. */
	share: number;
	/** 0 for the largest share, then 1, 2 … by size. */
	rank: number;
	/** The largest share: the plate in the ink color. */
	lead: boolean;
	color: string;
	/** A label inside the plate: the ground or the ink, whichever reads better on it. */
	ink: string;
}

export interface PlateGroup {
	name: string;
	plates: Plate[];
}

/**
 * A pie as plates (docs/ui-references/kori-v3): one row per share in the order of the spec, as
 * wide as the share. The largest wears the ink color, the rest step down the grey ladder by
 * size. A share that cannot draw stays out: empty, zero, below zero or too small for a pixel.
 */
export function toPlates(spec: ChartSpec, theme: ChartTheme): PlateGroup[] {
	return spec.series.map((series) => {
		const values = series.points.flatMap((p) =>
			p.y !== null && Number.isFinite(p.y) && p.y > 0 ? [{ label: String(p.x), value: p.y }] : []
		);
		const total = values.reduce((sum, { value }) => sum + value, 0);
		const drawn = values
			.map((entry) => ({ ...entry, share: entry.value / total }))
			.filter(({ share }) => share > 0);
		// Of two equal shares the first in the spec ranks higher.
		const order = drawn
			.map((_, i) => i)
			.sort((a, b) => (drawn[b]?.value ?? 0) - (drawn[a]?.value ?? 0) || a - b);
		const rankOf = new Map(order.map((index, rank) => [index, rank]));
		return {
			name: series.name,
			plates: drawn.map((entry, i) => {
				const rank = rankOf.get(i) ?? 0;
				const step = theme.ladder[Math.min(rank, theme.ladder.length) - 1];
				const color = rank === 0 ? theme.text : (step ?? theme.muted);
				const ink =
					contrast(color, theme.surface) >= contrast(color, theme.text)
						? theme.surface
						: theme.text;
				return { ...entry, rank, lead: rank === 0, color, ink };
			})
		};
	});
}
