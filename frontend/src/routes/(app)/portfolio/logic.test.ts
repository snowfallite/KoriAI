import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { BrokerAccountOut } from '$lib/types';
import {
	accountOf,
	accountResult,
	accountsHint,
	allocationChart,
	askHref,
	coverage,
	hero,
	PORTFOLIO_QUESTION,
	positionQuestion,
	pricesNote,
	summarize,
	tickerLine,
	withAccount,
	yieldText
} from './logic';
import type { Portfolio, Position } from './logic';

const NBSP = ' ';

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
		// docs/ui-references/kori-v4 (Портфель): «Структура портфеля  по типам инструментов».
		expect(spec.subtitle).toBe('по типам инструментов');
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

// tech.md S1-15 AC 6: the result «к средней цене покупки» and «N позиций на M счетах» stand
// on lines of their own, accounts by name.
describe('coverage', () => {
	const both = [account('acc1', '1', null, null), account('acc2', '1', null, null)];

	it('counts the positions over every account', () => {
		expect(coverage(10, both)).toBe('10 позиций на 2 счетах');
		expect(coverage(29, both)).toBe('29 позиций на 2 счетах');
		expect(coverage(1, both)).toBe('1 позиция на 2 счетах');
		expect(coverage(3, both)).toBe('3 позиции на 2 счетах');
	});

	it('names the one account it covers, never its alias', () => {
		expect(coverage(10, [account('acc2', '1', null, null)])).toBe(
			'10 позиций на счёте «Счёт acc2»'
		);
	});
});

describe('yieldText', () => {
	it('gives the result of every account in whole rubles', () => {
		const summary = summarize(
			portfolio({
				accounts: [account('acc1', '0', '34570', null), account('acc2', '0', '7520', null)]
			})
		);

		expect(yieldText(summary)).toBe(`+42${NBSP}090${NBSP}₽`);
	});

	it('adds the share of one account in brackets', () => {
		const summary = summarize(portfolio({ accounts: [account('acc1', '0', '34570', '0.0426')] }));

		expect(yieldText(summary)).toBe(`+34${NBSP}570${NBSP}₽ (+4,26${NBSP}%)`);
	});

	it('has no line without a result', () => {
		const summary = summarize(portfolio({ accounts: [account('acc1', '0', null, null)] }));

		expect(yieldText(summary)).toBeNull();
	});
});

describe('accountResult', () => {
	it('writes the result of an account with its share in brackets', () => {
		expect(accountResult(account('acc1', '846865', '34570', '0.0426'))).toBe(
			`+34${NBSP}570${NBSP}₽ (+4,26${NBSP}%)`
		);
		expect(accountResult(account('acc2', '1', '-6400', '-0.061'))).toBe(
			`−6${NBSP}400${NBSP}₽ (−6,10${NBSP}%)`
		);
		expect(accountResult(account('acc3', '1', '1250', null))).toBe(`+1${NBSP}250${NBSP}₽`);
		expect(accountResult(account('acc4', '1', null, null))).toBeNull();
	});
});

describe('pricesNote', () => {
	// The meta line of v4: the prices of T-Invest at the moment of the answer, Moscow time.
	it('dates the prices in Moscow time', () => {
		expect(pricesNote('2026-10-10T16:00:00Z')).toBe('Цены Т-Инвестиций на 10.10.2026, 19:00 МСК');
	});
});

describe('hero', () => {
	it('shows whole rubles and the sign of the ruble apart', () => {
		expect(hero({ amount: '4440857.62', currency: 'RUB' })).toEqual({
			number: `4${NBSP}440${NBSP}858`,
			unit: '₽'
		});
		expect(hero({ amount: '12', currency: 'USD' })).toEqual({ number: '12', unit: 'USD' });
	});
});

// tech.md §13.3: /chat?q=<текст> fills the question field and never sends it.
describe('askHref', () => {
	it('leaves the question in the query of the chat', () => {
		const url = new URL(askHref(PORTFOLIO_QUESTION), 'http://kori.test');

		expect(url.pathname).toBe('/chat');
		expect(url.searchParams.get('q')).toBe('Что с моим портфелем и почему?');
	});

	it('carries any question through the URL', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 1 }), (question) => {
				expect(new URL(askHref(question), 'http://kori.test').searchParams.get('q')).toBe(question);
			})
		);
	});
});

function position(
	name: string,
	yield_pct: string | null,
	fields: Partial<Position['instrument']> & { accrued?: string } = {}
): Position {
	const money = { amount: '1', currency: 'RUB' };
	const { accrued, ...instrument } = fields;
	return {
		instrument: {
			uid: '00000000-0000-0000-0000-000000000001',
			ticker: 'X',
			class_code: 'TQBR',
			name,
			instrument_type: 'share',
			currency: 'RUB',
			logo_url: null,
			brand_color: null,
			...instrument
		},
		account_alias: 'acc1',
		quantity: '1',
		avg_price: money,
		current_price: money,
		value: money,
		value_rub: money,
		weight: '0.1',
		yield_abs: yield_pct === null ? null : money,
		yield_pct,
		accrued_interest: accrued === undefined ? null : { amount: accrued, currency: 'RUB' }
	};
}

// The question a row leaves in the chat (S1-15 AC 6): a sentence, not a telegram; «позиция»
// keeps the verb right for any name (Т-Технологии, ОФЗ 26240).
describe('positionQuestion', () => {
	it('asks why a position grew or fell since the purchase', () => {
		expect(positionQuestion(position('Сбербанк', '0.176'))).toBe(
			`Почему позиция «Сбербанк» выросла на 17,6${NBSP}% с покупки?`
		);
		expect(positionQuestion(position('Газпром', '-0.147'))).toBe(
			`Почему позиция «Газпром» упала на 14,7${NBSP}% с покупки?`
		);
		expect(positionQuestion(position('Т-Технологии', '0.099'))).toBe(
			`Почему позиция «Т-Технологии» выросла на 9,9${NBSP}% с покупки?`
		);
	});

	it('asks about the position itself when it has no result or none to speak of', () => {
		expect(positionQuestion(position('Доллар США', null))).toBe('Что с позицией «Доллар США»?');
		expect(positionQuestion(position('ОФЗ 26240', '0.0004'))).toBe('Что с позицией «ОФЗ 26240»?');
	});
});

describe('tickerLine', () => {
	// docs/ui-references/kori-v4 (Портфель): «SU26240, НКД 8,20 ₽», a comma instead of a dot.
	it('adds the accrued interest of a bond after a comma', () => {
		expect(tickerLine(position('ОФЗ 26240', null, { ticker: 'SU26240', accrued: '8.2' }))).toBe(
			`SU26240, НКД 8,20${NBSP}₽`
		);
		expect(tickerLine(position('Сбербанк', null, { ticker: 'SBER' }))).toBe('SBER');
	});
});
