// Pure logic of the portfolio tab (tech.md §16.2): the account in the URL, the structure chart
// and the summary cards.
import type { components } from '$lib/api/schema';
import type { BrokerAccountOut, ChartSpec, Money } from '$lib/types';
import { formatNumber } from '$lib/utils/format';

export type Portfolio = components['schemas']['PortfolioOut'];
export type Position = Portfolio['positions'][number];
type Trend = 'up' | 'down' | 'flat';

export interface Summary {
	total: Money;
	/** The sum of the expected yields of the accounts in rubles; null when none has one. */
	yield: number | null;
	/** A share, given only for one account: T-Invest has no yield share of several. */
	yieldShare: string | null;
	trend: Trend;
}

const ALIAS = /^acc[0-9]+$/;
const PLURAL = new Intl.PluralRules('ru-RU');

/** The visible account the URL names (?account=acc2); null stands for every account, also
 * for an alias the user no longer has or has hidden. */
export function accountOf(url: URL, accounts: BrokerAccountOut[]): string | null {
	const alias = url.searchParams.get('account');
	const known = accounts.some((account) => account.alias === alias && !account.is_hidden);
	return alias !== null && ALIAS.test(alias) && known ? alias : null;
}

/** The query of the tab for one account (?account=acc2), or for every account. */
export function withAccount(url: URL, alias: string | null): string {
	const query = new URLSearchParams(url.search);
	if (alias === null) query.delete('account');
	else query.set('account', alias);
	const search = query.toString();
	return search ? `?${search}` : '';
}

/** The split by instrument type as a pie (tech.md §9.9). A slice below zero, such as a margin
 * debt in rubles, has no place on a pie: the positions table keeps it. */
export function allocationChart(portfolio: Portfolio): ChartSpec {
	const points = portfolio.allocation
		.filter((slice) => Number(slice.value.amount) > 0)
		.map((slice) => ({
			x: slice.label,
			y: Number(slice.value.amount),
			o: null,
			h: null,
			l: null,
			c: null,
			y_cat: null,
			z: null
		}));
	return {
		kind: 'pie',
		title: 'Структура портфеля',
		subtitle: 'По типам инструментов',
		x: { type: 'category', label: 'Тип', format: null, unit: null },
		y: { type: 'value', label: 'Стоимость', format: 'money', unit: portfolio.currency },
		y2: null,
		series: [{ name: 'Стоимость', points, axis: 'y', role: null }],
		source_ids: []
	};
}

export function summarize(portfolio: Portfolio): Summary {
	const yields = portfolio.accounts.flatMap((account) =>
		account.expected_yield ? [Number(account.expected_yield.amount)] : []
	);
	const sum = yields.length ? yields.reduce((total, amount) => total + amount, 0) : null;
	const [only] = portfolio.accounts;
	return {
		total: portfolio.total,
		yield: sum,
		yieldShare: portfolio.accounts.length === 1 && only ? only.expected_yield_pct : null,
		trend: sum === null || sum === 0 ? 'flat' : sum > 0 ? 'up' : 'down'
	};
}

/** «на 2 счетах»: the hint under the number of positions. */
export function accountsHint(count: number): string {
	const noun = PLURAL.select(count) === 'one' ? 'счёте' : 'счетах';
	return `на ${formatNumber(count, 0)} ${noun}`;
}
