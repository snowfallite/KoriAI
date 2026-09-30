import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { ChartSpec } from '$lib/types';
import { type ChartTheme, formatAxisValue, toEChartsOption } from './chart-option';

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

const theme: ChartTheme = {
	text: '#000000',
	muted: '#666666',
	grid: '#dbdbdb',
	surface: '#ffffff',
	font: 'monospace',
	series: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
	positive: '#117a37',
	negative: '#c8102e'
};

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

const validSpec: fc.Arbitrary<ChartSpec> = fc.constantFrom(...KINDS).chain((kind) =>
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
				role: fc.option(fc.constantFrom('primary', 'positive', 'negative', 'neutral', 'benchmark'))
			}),
			{ minLength: 1, maxLength: 12 }
		),
		source_ids: fc.array(fc.string(), { maxLength: 3 })
	})
);

function pt(fields: Partial<Point>): Point {
	return { x: '', y: null, o: null, h: null, l: null, c: null, y_cat: null, z: null, ...fields };
}

function spec(kind: Kind, series: Partial<Series>[], extra: Partial<ChartSpec> = {}): ChartSpec {
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
	};
}

// The option's series and axes may be one object or a list.
type Loose = Record<string, unknown>;
const list = (value: unknown): Loose[] =>
	value === undefined ? [] : ((Array.isArray(value) ? value : [value]) as Loose[]);
const seriesOf = (s: ChartSpec) => list(toEChartsOption(s, theme).series);

describe('toEChartsOption', () => {
	it('never throws on a valid spec and keeps the number of series', () => {
		fc.assert(
			fc.property(validSpec, (s) => {
				expect(seriesOf(s)).toHaveLength(s.series.length);
			}),
			{ numRuns: 300 }
		);
	});

	it('maps every kind to its series type', () => {
		const types = KINDS.map((kind) => {
			const p = pt({ x: 'a', y: 1, o: 1, h: 2, l: 0, c: 1.5, y_cat: 'b', z: 1 });
			return seriesOf(spec(kind, [{ points: [p] }]))[0]?.type;
		});
		expect(types).toEqual([
			'line',
			'line',
			'bar',
			'bar',
			'pie',
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
			theme.text,
			theme.series[1]
		]);
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

	it('turns pie points into named slices', () => {
		const points = [pt({ x: 'Акции', y: 60 }), pt({ x: 'Облигации', y: 40 })];
		const option = toEChartsOption(spec('pie', [{ points }]), theme);
		expect(list(option.series)[0]?.data).toEqual([
			{ name: 'Акции', value: 60 },
			{ name: 'Облигации', value: 40 }
		]);
		expect(option.xAxis).toBeUndefined();
	});

	it('keeps the hole of a donut inside it however many pies share the row', () => {
		for (const n of [1, 4, 12]) {
			for (const pie of seriesOf(
				spec(
					'pie',
					Array.from({ length: n }, () => ({}))
				)
			)) {
				const [inner = 0, outer = 0] = (pie.radius as string[]).map(Number.parseFloat);
				expect(inner).toBeLessThan(outer);
			}
		}
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

	it('centers a diverging heatmap scale on zero', () => {
		const points = [
			pt({ x: 'SBER', y_cat: 'GAZP', z: -0.4 }),
			pt({ x: 'SBER', y_cat: 'SBER', z: 1 })
		];
		const option = toEChartsOption(spec('heatmap', [{ points }]), theme);
		expect(list(option.visualMap)[0]).toMatchObject({ min: -1, max: 1 });
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
