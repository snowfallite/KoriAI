<script lang="ts">
	import type { ColumnDef } from '@tanstack/table-core';
	import DataTable from '$lib/components/DataTable.svelte';
	import MoneyText from '$lib/components/MoneyText.svelte';
	import PercentText from '$lib/components/PercentText.svelte';
	import { renderComponent, renderSnippet } from '$lib/ui/data-table';
	import type { Portfolio } from '../logic';

	type Account = Portfolio['accounts'][number];

	let { accounts }: { accounts: Account[] } = $props();

	const RIGHT = { class: 'text-right' };

	const columns: ColumnDef<Account>[] = [
		{ id: 'account', header: 'Счёт', accessorFn: (a) => `${a.alias} · ${a.name}` },
		{
			id: 'total',
			header: 'Стоимость',
			accessorFn: (a) => Number(a.total.amount),
			cell: ({ row }) => renderComponent(MoneyText, { money: row.original.total }),
			meta: RIGHT
		},
		{
			id: 'yield',
			header: 'Доходность',
			accessorFn: (a) => (a.expected_yield ? Number(a.expected_yield.amount) : undefined),
			cell: ({ row }) => renderSnippet(earned, row.original),
			sortUndefined: 'last',
			meta: RIGHT
		}
	];
</script>

{#snippet earned(account: Account)}
	{#if account.expected_yield}
		<MoneyText money={account.expected_yield} signed colorize />
		{#if account.expected_yield_pct !== null}
			<span class="block text-xs">
				<PercentText value={account.expected_yield_pct} signed colorize />
			</span>
		{/if}
	{:else}
		—
	{/if}
{/snippet}

<section aria-labelledby="accounts-title" class="space-y-2">
	<h2 id="accounts-title" class="text-xs tracking-wider text-muted-foreground uppercase">Счета</h2>
	<DataTable {columns} rows={accounts} dense />
</section>
