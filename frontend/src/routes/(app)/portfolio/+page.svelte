<script lang="ts">
	import PlugZap from '@lucide/svelte/icons/plug-zap';
	import { goto, invalidate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import AccountSelect from '$lib/components/AccountSelect.svelte';
	import ChartView from '$lib/components/ChartView.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import LoadingBlock from '$lib/components/LoadingBlock.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import { Button } from '$lib/ui/button';
	import { formatDate, formatMoney, formatNumber, formatPercent } from '$lib/utils/format';
	import AccountsTable from './components/AccountsTable.svelte';
	import PositionsTable from './components/PositionsTable.svelte';
	import { accountsHint, allocationChart, summarize, withAccount } from './logic';

	let { data } = $props();

	const visible = $derived(data.me.broker.accounts.filter((account) => !account.is_hidden));
	const current = $derived(visible.find((account) => account.alias === data.account));

	function selectAccount(alias: string | null) {
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- resolve() gives the path, the account query follows it
		void goto(`${resolve('/portfolio')}${withAccount(page.url, alias)}`, {
			keepFocus: true,
			noScroll: true
		});
	}
</script>

<svelte:head><title>Портфель · Kōri</title></svelte:head>

<div class="space-y-6">
	<PageHeader title="Портфель" description="Счета, структура и позиции">
		{#snippet actions()}
			{#if visible.length > 1}
				<AccountSelect accounts={visible} value={data.account} onChange={selectAccount} />
			{/if}
		{/snippet}
	</PageHeader>

	{#await data.portfolio}
		<div class="grid gap-4 md:grid-cols-3">
			<StatCard label="Стоимость портфеля" value="" loading />
			<StatCard label="Ожидаемая доходность" value="" loading />
			<StatCard label="Позиции" value="" loading />
		</div>
		<LoadingBlock variant="chart" />
		<LoadingBlock variant="table" rows={6} />
	{:then state}
		{#if state.kind === 'not_connected'}
			<EmptyState
				icon={PlugZap}
				title="Брокер не подключён"
				description="Подключите в Настройках токен Т-Инвестиций с доступом только на чтение: здесь появятся счета, структура и позиции."
			>
				{#snippet action()}
					<Button href={resolve('/settings')}>
						<span data-slot="button-glyph" aria-hidden="true">→</span>Подключить токен
					</Button>
				{/snippet}
			</EmptyState>
		{:else if state.kind === 'error'}
			<ErrorState error={state.error} onRetry={() => invalidate('app:portfolio')} />
		{:else}
			{@const portfolio = state.portfolio}
			{@const summary = summarize(portfolio)}
			<section aria-label="Итоги" class="grid gap-4 md:grid-cols-3">
				<StatCard
					label="Стоимость портфеля"
					value={formatMoney(summary.total.amount, summary.total.currency)}
					hint={current ? `${current.alias} · ${current.name}` : 'Все счета'}
				/>
				<StatCard
					label="Ожидаемая доходность"
					value={summary.yield === null ? '—' : formatMoney(summary.yield, 'RUB', { signed: true })}
					delta={summary.yieldShare === null
						? undefined
						: { text: formatPercent(summary.yieldShare, { signed: true }), trend: summary.trend }}
					hint="От средней цены покупки"
				/>
				<StatCard
					label="Позиции"
					value={formatNumber(portfolio.positions.length, 0)}
					hint={accountsHint(portfolio.accounts.length)}
				/>
			</section>
			<div class="grid gap-4 lg:grid-cols-2">
				<ChartView spec={allocationChart(portfolio)} height={280} />
				<AccountsTable accounts={portfolio.accounts} />
			</div>
			<PositionsTable positions={portfolio.positions} showAccount={portfolio.accounts.length > 1} />
			<p class="text-xs text-muted-foreground">
				Оценка на {formatDate(portfolio.as_of)} по ценам Т-Инвестиций
			</p>
		{/if}
	{/await}
</div>
