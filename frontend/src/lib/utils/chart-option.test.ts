import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { ChartSpec } from '$lib/types';
import {
	type CartesianSpec,
	type ChartTheme,
	formatAxisValue,
	isCartesian,
	toEChartsOption,
	toPlates
} from './chart-option';

type Kind = ChartSpec['kind'];
type Series = ChartSpec['series'][number];
type Point = Series['points'][number];

const KINDS: Kind[] = [
	'line',
	'area',
	'bar',
	'stacked_bar',
	'pie',
	'candlestick',
	'scatter',
	'heatmap',
	'waterfall'
];
const CARTESIAN = KINDS.filter((kind) => kind !== 'pie');

// Distinct stand-ins for every token, so a test can tell which one a mark wears.
const theme: ChartTheme = {
	text: '#f0f0f1',
	muted: '#a0a0a1',
	grid: '#1a1a1b',
	surface: '#000001',
	font: 'monospace',
	series: ['#ffffff', '#fe2627', '#aaaaaa', '#ffa5a5', '#757575', '#df342f', '#cbcbcb', '#4e4e4e'],
	positive: '#f0f0f2',
	negative: '#fe2628',
	primary: '#fe2629',
	ladder: ['#cbcbcc', '#aaaaab', '#757576']
};

const PALETTE = new Set([
	...theme.series,
	...theme.ladder,
	theme.text,
	theme.muted,
	theme.grid,
	theme.surface,
	theme.positive,
	theme.negative,
	theme.primary,
	'transparent'
]);

/** Every color an option names, however deep: series, items, axes, tooltip, scales. */
function colorsOf(value: unknown, found: string[] = []): string[] {
	if (Array.isArray(value)) {
		for (const item of value) colorsOf(item, found);
	} else if (value !== null && typeof value === 'object') {
		for (const [key, inner] of Object.entries(value)) {
			if (/color$/i.test(key) && typeof inner === 'string') found.push(inner);
			else if (/color$/i.test(key) && Array.isArray(inner))
				found.push(...inner.filter((c): c is string => typeof c === 'string'));
			else colorsOf(inner, found);
		}
	}
	return found;
}

const finite = fc.double({ min: -1e12, max: 1e12, noNaN: true });
const isoDay = fc
	.date({ min: new Date('2000-01-01'), max: new Date('2100-01-01'), noInvalidDate: true })
	.map((d) => d.toISOString().slice(0, 10));

const axis = fc.record({
	type: fc.constantFrom('time', 'category', 'value', 'log'),
	label: fc.option(fc.string()),
	format: fc.option(
		fc.constantFrom('date', 'month', 'quarter', 'year', 'money', 'percent', 'number', 'compact')
	),
	unit: fc.option(fc.constantFrom('RUB', 'USD', '%', 'x'))
});

/** Points valid for the kind: the ChartSpec validator of tech.md §9.9. */
function point(kind: Kind): fc.Arbitrary<Point> {
	const need = (field: 'y' | 'ohlc' | 'cell') =>
		field === 'y'
			? kind !== 'candlestick' && kind !== 'heatmap'
			: field === 'ohlc'
				? kind === 'candlestick'
				: kind === 'heatmap';
	const value = (needed: boolean) => (needed ? finite : fc.option(finite));
	return fc.record({
		x: fc.oneof(fc.string(), finite, isoDay),
		y: value(need('y')),
		o: value(need('ohlc')),
		h: value(need('ohlc')),
		l: value(need('ohlc')),
		c: value(need('ohlc')),
		y_cat: need('cell') ? fc.string() : fc.option(fc.string()),
		z: value(need('cell'))
	});
}

const specOf = (kinds: Kind[]): fc.Arbitrary<ChartSpec> =>
	fc.constantFrom(...kinds).chain((kind) =>
		fc.record({
			kind: fc.constant(kind),
			title: fc.string(),
			subtitle: fc.option(fc.string()),
			x: axis,
			y: axis,
			y2: fc.option(axis),
			series: fc.array(
				fc.record({
					name: fc.string(),
					points: fc.array(point(kind), { maxLength: kind === 'pie' ? 12 : 30 }),
					axis: fc.constantFrom('y', 'y2'),
					role: fc.option(
						fc.constantFrom('primary', 'positive', 'negative', 'neutral', 'benchmark')
					)
				}),
				{ minLength: 1, maxLength: 12 }
			),
			source_ids: fc.array(fc.string(), { maxLength: 3 })
		})
	);

const validSpec = specOf(CARTESIAN) as fc.Arbitrary<CartesianSpec>;
const pieSpec = specOf(['pie']);

function pt(fields: Partial<Point>): Point {
	return { x: '', y: null, o: null, h: null, l: null, c: null, y_cat: null, z: null, ...fields };
}

function spec(
	kind: Kind,
	series: Partial<Series>[],
	extra: Partial<ChartSpec> = {}
): CartesianSpec {
	const axisOf = (type: ChartSpec['x']['type']) => ({
		type,
		label: null,
		format: null,
		unit: null
	});
	return {
		kind,
		title: 'График',
		subtitle: null,
		x: axisOf('category'),
		y: axisOf('value'),
		y2: null,
		series: series.map((s, i) => ({ name: `s${i}`, points: [], axis: 'y', role: null, ...s })),
		source_ids: [],
		...extra
	} as CartesianSpec;
}

// The option's series and axes may be one object or a list.
type Loose = Record<string, unknown>;
const list = (value: unknown): Loose[] =>
	value === undefined ? [] : ((Array.isArray(value) ? value : [value]) as Loose[]);
const seriesOf = (s: CartesianSpec) => list(toEChartsOption(s, theme).series);
/** The color a data item wears: its own, or the color of its series. */
function itemColor(series: Loose | undefined, i: number): unknown {
	const item = list(series?.data)[i] as { itemStyle?: { color?: unknown } } | undefined;
	return item?.itemStyle?.color ?? series?.color;
}

describe('toEChartsOption', () => {
	it('never throws on a valid spec and keeps the number of series', () => {
		fc.assert(
			fc.property(validSpec, (s) => {
				expect(seriesOf(s)).toHaveLength(s.series.length);
			}),
			{ numRuns: 300 }
		);
	});

	it('maps every cartesian kind to its series type', () => {
		const types = CARTESIAN.map((kind) => {
			const p = pt({ x: 'a', y: 1, o: 1, h: 2, l: 0, c: 1.5, y_cat: 'b', z: 1 });
			return seriesOf(spec(kind, [{ points: [p] }]))[0]?.type;
		});
		expect(types).toEqual([
			'line',
			'line',
			'bar',
			'bar',
			'candlestick',
			'scatter',
			'heatmap',
			'custom'
		]);
	});

	it('gives categorical slots in order and fixed colors to roles', () => {
		const series = seriesOf(
			spec('line', [{ role: 'positive' }, {}, { role: 'benchmark' }, { role: 'primary' }])
		);
		expect(series.map((s) => s.color)).toEqual([
			theme.positive,
			theme.series[0],
			theme.muted,
			theme.series[1]
		]);
	});

	// S1-14 AC 2: the charts speak only the brand palette of tech.md §13.3.
	it('names no color outside the palette', () => {
		fc.assert(
			fc.property(validSpec, (s) => {
				for (const color of colorsOf(toEChartsOption(s, theme))) expect(PALETTE).toContain(color);
			}),
			{ numRuns: 300 }
		);
	});

	it('draws a benchmark as a grey dash, whatever its slot', () => {
		const [, benchmark] = seriesOf(spec('line', [{}, { role: 'benchmark' }]));
		expect(benchmark?.color).toBe(theme.muted);
		expect(benchmark?.lineStyle).toMatchObject({ type: [4, 4] });
	});

	it('paints every loss red: bars, stacked bars and the falls of candles', () => {
		const points = [pt({ x: 'SBER', y: 28050 }), pt({ x: 'GAZP', y: -23800 })];
		for (const kind of ['bar', 'stacked_bar'] as const) {
			const [series] = seriesOf(spec(kind, [{ points }]));
			expect(itemColor(series, 0)).toBe(theme.series[0]);
			expect(itemColor(series, 1)).toBe(theme.negative);
		}
		const candle = pt({ x: 'a', o: 2, h: 3, l: 1, c: 1 });
		const [candles] = seriesOf(spec('candlestick', [{ points: [candle] }]));
		expect(candles?.itemStyle).toMatchObject({
			color0: theme.negative,
			borderColor0: theme.negative
		});
	});

	it('paints a falling waterfall step red and a rising one in the ink color', () => {
		const points = [pt({ x: 'Выручка', y: 100 }), pt({ x: 'Расходы', y: -30 })];
		const [series] = seriesOf(spec('waterfall', [{ points }]));
		type Render = (params: unknown, api: unknown) => { style: { fill: string } };
		const render = series?.renderItem as Render;
		const fill = (i: number) => {
			const step = list(series?.data)[i] as unknown as number[];
			const api = {
				value: (dim: number) => step[dim],
				coord: ([x, y]: number[]) => [x, y],
				size: () => [10, 0]
			};
			return render({}, api).style.fill;
		};
		expect([fill(0), fill(1)]).toEqual([theme.positive, theme.negative]);
	});

	it('runs correlations from grey through the ground to red', () => {
		const points = [
			pt({ x: 'SBER', y_cat: 'GAZP', z: -0.4 }),
			pt({ x: 'SBER', y_cat: 'SBER', z: 1 })
		];
		const option = toEChartsOption(spec('heatmap', [{ points }]), theme);
		expect(list(option.visualMap)[0]).toMatchObject({
			min: -1,
			max: 1,
			inRange: { color: [theme.ladder.at(-1), theme.surface, theme.primary] }
		});
	});

	it('shows a legend for two series and more, never for one', () => {
		expect(toEChartsOption(spec('line', [{}, {}]), theme).legend).toMatchObject({ show: true });
		expect(toEChartsOption(spec('line', [{}]), theme).legend).toMatchObject({ show: false });
	});

	it('washes an area and stacks a stacked bar', () => {
		expect(seriesOf(spec('area', [{}]))[0]?.areaStyle).toMatchObject({ opacity: 0.1 });
		const stacks = seriesOf(spec('stacked_bar', [{}, {}, {}])).map((s) => s.stack);
		expect(new Set(stacks).size).toBe(1);
		expect(stacks[0]).toBeTruthy();
	});

	it('puts a calendar day of a time axis at UTC midnight, so it reads the same day anywhere', () => {
		const time = { type: 'time' as const, label: null, format: 'date' as const, unit: null };
		const points = [pt({ x: '2026-01-05', y: 1 })];
		expect(seriesOf(spec('line', [{ points }], { x: time }))[0]?.data).toEqual([
			[Date.UTC(2026, 0, 5), 1]
		]);
		expect(formatAxisValue(Date.UTC(2026, 0, 5), time)).toBe('05.01.2026');
	});

	it('orders candle values as ECharts reads them: open, close, low, high', () => {
		const points = [pt({ x: '2026-09-29', o: 10, h: 12, l: 9, c: 11 })];
		expect(seriesOf(spec('candlestick', [{ points }]))[0]?.data).toEqual([
			['2026-09-29', 10, 11, 9, 12]
		]);
	});

	it('stacks waterfall steps from the running total', () => {
		const points = [
			pt({ x: 'Выручка', y: 100 }),
			pt({ x: 'Расходы', y: -30 }),
			pt({ x: 'Прочее', y: 20 })
		];
		expect(seriesOf(spec('waterfall', [{ points }]))[0]?.data).toEqual([
			[0, 0, 100, 100],
			[1, 100, 70, -30],
			[2, 70, 90, 20]
		]);
	});

	it('puts y2 series on the second axis only when the spec has one', () => {
		const axisOf = { type: 'value' as const, label: null, format: null, unit: null };
		const withY2 = toEChartsOption(spec('line', [{}, { axis: 'y2' }], { y2: axisOf }), theme);
		expect(list(withY2.yAxis)).toHaveLength(2);
		expect(list(withY2.series).map((s) => s.yAxisIndex)).toEqual([0, 1]);

		const without = toEChartsOption(spec('line', [{}, { axis: 'y2' }]), theme);
		expect(list(without.yAxis)).toHaveLength(1);
		expect(list(without.series).map((s) => s.yAxisIndex)).toEqual([0, 0]);
	});
});

describe('isCartesian', () => {
	it('sends a pie to the plates and every other kind to ECharts', () => {
		expect(KINDS.filter((kind) => !isCartesian(spec(kind, [{}])))).toEqual(['pie']);
	});
});

// A pie draws as plates: one row per share, as wide as the share (docs/ui-references/kori-v3).
describe('toPlates', () => {
	it('gives the largest share the ink color and the rest the grey ladder by size', () => {
		const points = [
			pt({ x: 'Облигации', y: 220710 }),
			pt({ x: 'Акции', y: 820485 }),
			pt({ x: 'Валюта', y: 48200 }),
			pt({ x: 'Фонды', y: 105750 })
		];
		const [group] = toPlates(spec('pie', [{ name: 'Стоимость', points }]), theme);

		expect(group?.name).toBe('Стоимость');
		expect(group?.plates.map((p) => [p.label, p.color, p.lead])).toEqual([
			['Облигации', theme.ladder[0], false],
			['Акции', theme.text, true],
			['Валюта', theme.ladder[2], false],
			['Фонды', theme.ladder[1], false]
		]);
		expect(group?.plates[1]?.share).toBeCloseTo(820485 / 1195145, 12);
	});

	it('keeps every plate in the palette, its share in (0, 1] and the shares summing to 1', () => {
		fc.assert(
			fc.property(pieSpec, (s) => {
				const groups = toPlates(s, theme);
				expect(groups).toHaveLength(s.series.length);
				for (const group of groups) {
					for (const plate of group.plates) {
						expect(PALETTE).toContain(plate.color);
						expect(plate.value).toBeGreaterThan(0);
						expect(plate.share).toBeGreaterThan(0);
						expect(plate.share).toBeLessThanOrEqual(1);
					}
					if (group.plates.length) {
						const total = group.plates.reduce((sum, p) => sum + p.share, 0);
						expect(total).toBeCloseTo(1, 9);
						expect(group.plates.filter((p) => p.lead)).toHaveLength(1);
					}
				}
			}),
			{ numRuns: 300 }
		);
	});

	it('leaves out a share it cannot draw: empty, zero or below zero', () => {
		const points = [
			pt({ x: 'Акции', y: 10 }),
			pt({ x: 'Долг', y: -4 }),
			pt({ x: 'Ноль', y: 0 }),
			pt({ x: 'Пусто' })
		];
		const [group] = toPlates(spec('pie', [{ points }]), theme);

		expect(group?.plates.map((p) => p.label)).toEqual(['Акции']);
	});
});
