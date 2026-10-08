import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { BrokerAccountOut } from '$lib/types';
import { accountOf, accountsHint, allocationChart, summarize, withAccount } from './logic';
import type { Portfolio } from './logic';

const BASE = 'http://localhost/portfolio';

function brokerAccount(alias: string, is_hidden = false): BrokerAccountOut {
	return { alias, name: alias, type: 'broker', status: 'open', opened_at: null, is_hidden };
}

const ACCOUNTS = [brokerAccount('acc1'), brokerAccount('acc2'), brokerAccount('acc3', true)];

function account(
	alias: string,
	total: string,
	expected_yield: string | null,
	expected_yield_pct: string | null
): Portfolio['accounts'][number] {
	return {
		alias,
		name: `Счёт ${alias}`,
		total: { amount: total, currency: 'RUB' },
		expected_yield: expected_yield === null ? null : { amount: expected_yield, currency: 'RUB' },
		expected_yield_pct
	};
}

function slice(
	key: Portfolio['allocation'][number]['key'],
	label: string,
	value: string,
	weight: string
): Portfolio['allocation'][number] {
	return { key, label, value: { amount: value, currency: 'RUB' }, weight };
}

function portfolio(fields: Partial<Portfolio> = {}): Portfolio {
	return {
		as_of: '2026-10-02T16:00:00Z',
		currency: 'RUB',
		total: { amount: '1500', currency: 'RUB' },
		accounts: [account('acc1', '1000', '120.5', '0.137'), account('acc2', '500', '-20', '-0.04')],
		allocation: [
			slice('share', 'Акции', '1200', '0.8'),
			slice('bond', 'Облигации', '400', '0.2666'),
			slice('currency', 'Валюта', '-100', '-0.0666')
		],
		positions: [],
		...fields
	};
}

describe('accountOf', () => {
	it('reads the alias of a visible account from the query', () => {
		expect(accountOf(new URL(`${BASE}?account=acc2`), ACCOUNTS)).toBe('acc2');
	});

	it('takes every account for no alias, a stray one or a hidden one', () => {
		// An old link must not end in an error: the tab shows every account instead.
		for (const query of ['', '?account=all', '?account=acc', '?account=acc9', '?account=acc3']) {
			expect(accountOf(new URL(`${BASE}${query}`), ACCOUNTS)).toBeNull();
		}
	});
});

describe('withAccount', () => {
	it('puts the alias into the query and drops it for every account', () => {
		expect(withAccount(new URL(BASE), 'acc2')).toBe('?account=acc2');
		expect(withAccount(new URL(`${BASE}?account=acc2`), null)).toBe('');
	});

	it('keeps the other parameters', () => {
		expect(withAccount(new URL(`${BASE}?tab=risk`), 'acc1')).toBe('?tab=risk&account=acc1');
	});

	it('round-trips through accountOf', () => {
		const known = Array.from({ length: 12 }, (_, i) => brokerAccount(`acc${i + 1}`));
		const alias = fc.option(fc.constantFrom(...known.map((account) => account.alias)));
		fc.assert(
			fc.property(alias, fc.constantFrom(BASE, `${BASE}?account=acc7`), (wanted, from) => {
				const next = new URL(withAccount(new URL(from), wanted), BASE);
				expect(accountOf(next, known)).toBe(wanted);
			})
		);
	});
});

describe('allocationChart', () => {
	it('draws the positive slices as a pie in rubles', () => {
		const spec = allocationChart(portfolio());

		expect(spec.kind).toBe('pie');
		expect(spec.title).toBe('Структура портфеля');
		expect(spec.y).toMatchObject({ format: 'money', unit: 'RUB' });
		expect(spec.series).toHaveLength(1);
		// A margin debt has no place on a pie: the table keeps it.
		expect(spec.series[0]?.points.map((p) => [p.x, p.y])).toEqual([
			['Акции', 1200],
			['Облигации', 400]
		]);
	});

	it('keeps one empty series for an empty portfolio', () => {
		const spec = allocationChart(portfolio({ allocation: [] }));

		expect(spec.series).toHaveLength(1);
		expect(spec.series[0]?.points).toEqual([]);
	});
});

describe('summarize', () => {
	it('adds up the yields of the accounts', () => {
		const summary = summarize(portfolio());

		expect(summary.total).toEqual({ amount: '1500', currency: 'RUB' });
		expect(summary.yield).toBeCloseTo(100.5, 9);
		expect(summary.trend).toBe('up');
		// T-Invest gives no yield share of several accounts together.
		expect(summary.yieldShare).toBeNull();
	});

	it('gives the yield share of one account', () => {
		const summary = summarize(portfolio({ accounts: [account('acc2', '500', '-20', '-0.04')] }));

		expect(summary.yield).toBe(-20);
		expect(summary.yieldShare).toBe('-0.04');
		expect(summary.trend).toBe('down');
	});

	it('has no yield when no account has one', () => {
		const summary = summarize(
			portfolio({ accounts: [account('acc1', '0', null, null), account('acc2', '0', null, null)] })
		);

		expect(summary.yield).toBeNull();
		expect(summary.trend).toBe('flat');
	});

	it('sums any yields exactly enough for kopecks', () => {
		const kopecks = fc.integer({ min: -1e11, max: 1e11 });
		fc.assert(
			fc.property(fc.array(kopecks, { minLength: 1, maxLength: 10 }), (amounts) => {
				const accounts = amounts.map((k, i) =>
					account(`acc${i + 1}`, '0', (k / 100).toFixed(2), null)
				);
				const expected = amounts.reduce((sum, k) => sum + k, 0);
				expect(Math.round((summarize(portfolio({ accounts })).yield ?? NaN) * 100)).toBe(expected);
			})
		);
	});
});

describe('accountsHint', () => {
	it('declines the noun by the number', () => {
		expect(accountsHint(1)).toBe('на 1 счёте');
		expect(accountsHint(2)).toBe('на 2 счетах');
		expect(accountsHint(5)).toBe('на 5 счетах');
		expect(accountsHint(11)).toBe('на 11 счетах');
		expect(accountsHint(21)).toBe('на 21 счёте');
	});
});
