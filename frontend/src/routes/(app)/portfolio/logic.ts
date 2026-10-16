// Pure logic of the portfolio tab (tech.md §16.2): the account in the URL, the structure chart,
// the totals and the questions the tab leaves in the chat.
import type { components } from '$lib/api/schema';
import type { BrokerAccountOut, ChartSpec, Money } from '$lib/types';
import { formatNumber, formatPercent } from '$lib/utils/format';

export type Portfolio = components['schemas']['PortfolioOut'];
export type Position = Portfolio['positions'][number];
export type Account = Portfolio['accounts'][number];
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

const POSITIONS: Record<string, string> = { one: 'позиция', few: 'позиции', many: 'позиций' };

/** What the total covers: «29 позиций на 2 счетах», or the one account: «10 позиций · acc2 · ИИС». */
export function coverage(positions: number, accounts: Pick<Account, 'alias' | 'name'>[]): string {
	const count = `${formatNumber(positions, 0)} ${POSITIONS[PLURAL.select(positions)] ?? 'позиции'}`;
	const [only] = accounts;
	return accounts.length === 1 && only
		? `${count} · ${only.alias} · ${only.name}`
		: `${count} ${accountsHint(accounts.length)}`;
}

/** The total of the hero in whole units, its currency sign apart (docs/ui-references/kori-v3). */
export function hero(money: Money): { number: string; unit: string } {
	return {
		number: formatNumber(money.amount, 0),
		unit: money.currency === 'RUB' ? '₽' : money.currency
	};
}

export const PORTFOLIO_QUESTION = 'Что с моим портфелем и почему?';

/** The chat with a question waiting in its field (tech.md §13.3: /chat?q= fills, never sends). */
export function askHref(question: string): string {
	return `/chat?${new URLSearchParams({ q: question })}`;
}

/** The question a row of the positions asks: why it moved since the purchase. */
export function positionQuestion(position: Position): string {
	const name = position.instrument.name;
	return position.yield_pct === null
		? `Что с позицией «${name}»?`
		: `Почему ${name} ${formatPercent(position.yield_pct, { signed: true, digits: 1 })} с покупки?`;
}
