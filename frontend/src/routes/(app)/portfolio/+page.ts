import { api, ok } from '$lib/api/client';
import type { ApiError } from '$lib/types';
import type { PageLoad } from './$types';
import { accountOf, type Portfolio } from './logic';

export type PortfolioState =
	| { kind: 'ready'; portfolio: Portfolio }
	| { kind: 'not_connected' }
	| { kind: 'error'; error: ApiError };

async function fetchPortfolio(account: string | null): Promise<PortfolioState> {
	try {
		const query = account === null ? {} : { account };
		const portfolio = await ok(api.GET('/api/portfolio', { params: { query } }));
		return { kind: 'ready', portfolio };
	} catch (error) {
		const failure = error as ApiError;
		// The broker may have left in another tab since the layout asked (tech.md §6.4: 409).
		if (failure.code === 'broker_not_connected') return { kind: 'not_connected' };
		return { kind: 'error', error: failure };
	}
}

// The tab shows at once and the portfolio follows: T-Invest may take a few seconds.
export const load: PageLoad = async ({ url, parent, depends }) => {
	depends('app:portfolio');
	const { me } = await parent();
	const account = accountOf(url, me.broker.accounts);
	// Without a broker there is nothing to ask the API for.
	const portfolio: Promise<PortfolioState> = me.broker.connected
		? fetchPortfolio(account)
		: Promise.resolve({ kind: 'not_connected' });
	return { account, portfolio };
};
