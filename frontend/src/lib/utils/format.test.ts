import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
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

const NBSP = '\u00a0';

// A DecimalStr of the API (tech.md §6.1): up to 15 integer digits, up to 9 decimals.
const decimalStr = fc
	.tuple(fc.boolean(), fc.bigInt({ min: 0n, max: 10n ** 15n }), fc.stringMatching(/^\d{0,9}$/))
	.map(([negative, int, frac]) => `${negative ? '-' : ''}${int}${frac ? `.${frac}` : ''}`);

/** The decimal times 10^digits, rounded half away from zero as Intl does by default. */
function rounded(decimal: string, digits: number): bigint {
	const negative = decimal.startsWith('-');
	const [int = '0', frac = ''] = decimal.replace('-', '').split('.');
	const kept = frac.padEnd(digits + 1, '0');
	let scaled = BigInt(int + kept.slice(0, digits));
	if (Number(kept[digits]) >= 5) scaled += 1n;
	return negative ? -scaled : scaled;
}

/** Reads a formatted number back as an integer of 10^-digits units. */
function scaled(text: string, digits: number): bigint {
	const match = /^([+\u2212-]?)(\d+)(?:,(\d+))?/.exec(text.replace(/[\s\u00a0\u202f]/g, ''));
	if (!match) throw new Error(`not a number: ${text}`);
	const value = BigInt((match[2] ?? '') + (match[3] ?? '').padEnd(digits, '0'));
	return match[1] === '+' || match[1] === '' ? value : -value;
}

const SCALE: Record<string, number> = { 'тыс.': 1e3, млн: 1e6, млрд: 1e9, трлн: 1e12 };

/** Reads a compact number back: '1,25 млн' is 1 250 000. */
function compactValue(text: string): number {
	const match = /^([\u2212-]?)([\d\s\u00a0\u202f]+(?:,\d+)?)\s*(тыс\.|млн|млрд|трлн)?$/.exec(text);
	if (!match) throw new Error(`not a compact number: ${text}`);
	const value = Number((match[2] ?? '').replace(/[\s\u00a0\u202f]/g, '').replace(',', '.'));
	return (match[1] ? -value : value) * (SCALE[match[3] ?? ''] ?? 1);
}

/** Moscow has kept UTC+3 all year since 2014-10-26. */
function moscow(date: Date): Date {
	return new Date(date.getTime() + 3 * 3600 * 1000);
}

const pad = (n: number) => String(n).padStart(2, '0');
const instant = fc.date({
	min: new Date('2014-10-26T00:00:00Z'),
	max: new Date('2100-12-31T00:00:00Z'),
	noInvalidDate: true
});

describe('format.ts never throws', () => {
	const formatters = [
		(v: never) => formatNumber(v),
		(v: never) => formatMoney(v, v),
		(v: never) => formatPercent(v),
		(v: never) => formatCompact(v),
		(v: never) => formatDate(v),
		(v: never) => formatMonth(v),
		(v: never) => formatQuarter(v),
		(v: never) => formatYear(v)
	];

	it('returns a string for any input', () => {
		fc.assert(
			fc.property(fc.anything(), (value) => {
				for (const format of formatters) expect(typeof format(value as never)).toBe('string');
			})
		);
	});

	it('shows a dash for values that are not numbers or dates', () => {
		for (const bad of ['', 'abc', '1,5', 'NaN', null, undefined, Number.NaN, Infinity]) {
			expect(formatNumber(bad as never)).toBe('—');
			expect(formatMoney(bad as never, 'RUB')).toBe('—');
			expect(formatPercent(bad as never)).toBe('—');
			expect(formatCompact(bad as never)).toBe('—');
			expect(formatDate(bad as never)).toBe('—');
		}
	});
});

describe('formatMoney', () => {
	it('prints rubles the Russian way', () => {
		expect(formatMoney('1250000', 'RUB')).toBe(`1${NBSP}250${NBSP}000,00${NBSP}₽`);
		expect(formatMoney('-1250.5', 'RUB')).toBe(`\u22121${NBSP}250,50${NBSP}₽`);
		expect(formatMoney('1250.5', 'RUB', { signed: true })).toBe(`+1${NBSP}250,50${NBSP}₽`);
		expect(formatMoney('0', 'RUB', { signed: true })).toBe(`0,00${NBSP}₽`);
		expect(formatMoney('1250000', 'RUB', { compact: true })).toBe(`1,25${NBSP}млн${NBSP}₽`);
	});

	it('never prints a minus for an amount that rounds to zero', () => {
		expect(formatMoney('-0.001', 'RUB')).toBe(`0,00${NBSP}₽`);
	});

	it('falls back to the code when Intl does not know the currency', () => {
		expect(formatMoney('5', 'RUBX')).toBe(`5,00${NBSP}RUBX`);
	});

	it('reads back as the amount rounded to kopecks', () => {
		fc.assert(
			fc.property(decimalStr, fc.boolean(), (amount, signed) => {
				expect(scaled(formatMoney(amount, 'RUB', { signed }), 2)).toBe(rounded(amount, 2));
			})
		);
	});
});

describe('formatNumber', () => {
	it('reads back as the value rounded to the requested digits', () => {
		fc.assert(
			fc.property(decimalStr, fc.integer({ min: 0, max: 6 }), (value, digits) => {
				expect(scaled(formatNumber(value, digits), digits)).toBe(rounded(value, digits));
			})
		);
	});

	it('keeps up to two decimals by default', () => {
		expect(formatNumber('1234.5678')).toBe(`1${NBSP}234,57`);
		expect(formatNumber(10)).toBe('10');
	});
});

describe('formatPercent', () => {
	it('prints a share as percents', () => {
		expect(formatPercent('0.1234')).toBe(`12,34${NBSP}%`);
		expect(formatPercent(-0.05, { signed: true, digits: 1 })).toBe(`\u22125,0${NBSP}%`);
		expect(formatPercent('0.05', { signed: true })).toBe(`+5,00${NBSP}%`);
	});

	it('reads back as the share rounded to the requested digits', () => {
		fc.assert(
			fc.property(decimalStr, fc.integer({ min: 0, max: 4 }), (share, digits) => {
				const percent = scaled(formatPercent(share, { digits }), digits);
				// share × 100 at `digits` decimals is the share at `digits + 2` decimals.
				expect(percent).toBe(rounded(share, digits + 2));
			})
		);
	});
});

describe('formatCompact', () => {
	it('shortens big numbers with Russian suffixes', () => {
		expect(formatCompact(1_250_000)).toBe(`1,25${NBSP}млн`);
		expect(formatCompact('12500')).toBe(`12,5${NBSP}тыс.`);
		expect(formatCompact(-3_400_000_000)).toBe(`\u22123,4${NBSP}млрд`);
		expect(formatCompact(999)).toBe('999');
	});

	it('reads back within three significant digits', () => {
		const value = fc
			.double({ min: -1e15, max: 1e15, noNaN: true })
			.filter((v) => v === 0 || Math.abs(v) >= 1e-4);
		fc.assert(
			fc.property(value, (v) => {
				expect(Math.abs(compactValue(formatCompact(v)) - v)).toBeLessThanOrEqual(
					Math.abs(v) * 0.005 + 1e-12
				);
			})
		);
	});
});

describe('dates in Moscow time', () => {
	it('prints dd.MM.yyyy of the Moscow day', () => {
		expect(formatDate('2026-09-29T21:30:00Z')).toBe('30.09.2026');
		expect(formatDate('2026-09-30')).toBe('30.09.2026');
		expect(formatMonth('2026-09-29T21:30:00Z')).toBe('09.2026');
		expect(formatQuarter('2026-09-30')).toBe('3 кв. 2026');
		expect(formatYear('2026-12-31T21:30:00Z')).toBe('2027');
	});

	it('matches the calendar in UTC+3 for any instant', () => {
		fc.assert(
			fc.property(instant, (date) => {
				const m = moscow(date);
				const [day, month, year] = [m.getUTCDate(), m.getUTCMonth() + 1, m.getUTCFullYear()];
				for (const value of [date.toISOString(), date.getTime(), date]) {
					expect(formatDate(value)).toBe(`${pad(day)}.${pad(month)}.${year}`);
					expect(formatMonth(value)).toBe(`${pad(month)}.${year}`);
					expect(formatQuarter(value)).toBe(`${Math.ceil(month / 3)} кв. ${year}`);
					expect(formatYear(value)).toBe(String(year));
				}
			})
		);
	});

	it('keeps a calendar date as it is', () => {
		fc.assert(
			fc.property(instant, (date) => {
				const iso = date.toISOString().slice(0, 10);
				const [year, month, day] = iso.split('-');
				expect(formatDate(iso)).toBe(`${day}.${month}.${year}`);
			})
		);
	});
});
