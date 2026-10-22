<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import AccountSelect from '$lib/components/AccountSelect.svelte';
	import ChartView from '$lib/components/ChartView.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import LoadingBlock from '$lib/components/LoadingBlock.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Button } from '$lib/ui/button';
	import { Skeleton } from '$lib/ui/skeleton';
	import type { PortfolioState } from './+page';
	import AccountsList from './components/AccountsList.svelte';
	import PositionsTable from './components/PositionsTable.svelte';
	import Totals from './components/Totals.svelte';
	import { allocationChart, coverage, pricesNote, summarize, withAccount } from './logic';

	let { data } = $props();

	/** The load the tab waits for: the header and the body read one answer, and a new account or
	 * a retry starts over while the header and its tabs stay in place. */
	class Load {
		state = $state<PortfolioState>();
		constructor(promise: Promise<PortfolioState>) {
			void promise.then((answer) => (this.state = answer));
		}
	}

	const load = $derived(new Load(data.portfolio));
	const result = $derived(load.state);
	const visible = $derived(data.me.broker.accounts.filter((account) => !account.is_hidden));
	const asOf = $derived(result?.kind === 'ready' ? result.portfolio.as_of : null);

	function selectAccount(alias: string | null) {
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- resolve() gives the path, the account query follows it
		void goto(`${resolve('/portfolio')}${withAccount(page.url, alias)}`, {
			keepFocus: true,
			noScroll: true
		});
	}
</script>

<svelte:head><title>Портфель · Kōri</title></svelte:head>

<PageHeader title="Портфель" description={asOf ? pricesNote(asOf) : undefined}>
	{#snippet actions()}
		{#if visible.length > 1}
			<AccountSelect accounts={visible} value={data.account} onChange={selectAccount} />
		{/if}
	{/snippet}
</PageHeader>

{#if !result}
	<div role="status" class="border-b px-4 pt-10 pb-10 md:px-12 md:pt-16 md:pb-14">
		<span class="sr-only">Загрузка</span>
		<Skeleton class="h-4 w-40" />
		<Skeleton class="mt-[18px] h-[52px] w-72 md:h-[88px] md:w-[480px]" />
	</div>
	<div class="grid gap-12 border-b p-4 md:grid-cols-2 md:p-12">
		<LoadingBlock variant="table" rows={2} />
		<LoadingBlock variant="chart" />
	</div>
	<div class="p-4 md:p-12">
		<LoadingBlock variant="table" rows={6} />
	</div>
{:else if result.kind === 'not_connected'}
	<div class="p-4 md:p-12">
		<!-- The token field lives in the settings (F-01): the main action of the empty tab. -->
		<EmptyState
			title="Т-Инвестиции не подключены"
			description="Подключите токен в Настройках: здесь появятся счета, структура и позиции."
		>
			{#snippet action()}
				<Button href={resolve('/settings')}>
					<span data-slot="button-glyph" aria-hidden="true">→</span>Открыть настройки
				</Button>
			{/snippet}
		</EmptyState>
	</div>
{:else if result.kind === 'error'}
	<div class="p-4 md:p-12">
		<ErrorState error={result.error} onRetry={() => invalidate('app:portfolio')} />
	</div>
{:else}
	{@const portfolio = result.portfolio}
	<Totals
		label={data.account ? 'Стоимость счёта' : 'Стоимость портфеля'}
		summary={summarize(portfolio)}
		caption={coverage(portfolio.positions.length, portfolio.accounts)}
	/>
	<section
		aria-label="Счета и структура"
		class="grid grid-cols-[repeat(auto-fit,minmax(min(440px,100%),1fr))] gap-x-16 gap-y-12 border-b p-4 md:p-12"
	>
		<AccountsList accounts={portfolio.accounts} />
		<ChartView spec={allocationChart(portfolio)} />
	</section>
	<PositionsTable positions={portfolio.positions} accounts={portfolio.accounts} />
{/if}
