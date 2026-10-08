<script lang="ts">
	import type { ColumnDef } from '@tanstack/table-core';
	import DataTable from '$lib/components/DataTable.svelte';
	import InstrumentBadge from '$lib/components/InstrumentBadge.svelte';
	import MoneyText from '$lib/components/MoneyText.svelte';
	import PercentText from '$lib/components/PercentText.svelte';
	import { renderComponent, renderSnippet } from '$lib/ui/data-table';
	import { formatNumber } from '$lib/utils/format';
	import type { Position } from '../logic';

	let { positions, showAccount }: { positions: Position[]; showAccount: boolean } = $props();

	const RIGHT = { class: 'text-right' };
	const amount = (money: { amount: string } | null) => (money ? Number(money.amount) : undefined);

	// Numbers sort by value; an empty cell is undefined and goes last both ways.
	const columns = $derived<ColumnDef<Position>[]>([
		{
			id: 'instrument',
			header: 'Инструмент',
			accessorFn: (p) => p.instrument.name,
			cell: ({ row }) => renderComponent(InstrumentBadge, { instrument: row.original.instrument })
		},
		...(showAccount
			? [{ id: 'account', header: 'Счёт', accessorFn: (p: Position) => p.account_alias }]
			: []),
		{
			id: 'quantity',
			header: 'Количество',
			accessorFn: (p) => Number(p.quantity),
			cell: ({ row }) => formatNumber(row.original.quantity),
			meta: RIGHT
		},
		{
			id: 'price',
			header: 'Цена',
			accessorFn: (p) => amount(p.current_price),
			cell: ({ row }) => renderSnippet(price, row.original),
			sortUndefined: 'last',
			meta: RIGHT
		},
		{
			id: 'value_rub',
			header: 'Стоимость',
			accessorFn: (p) => Number(p.value_rub.amount),
			cell: ({ row }) => renderSnippet(value, row.original),
			meta: RIGHT
		},
		{
			id: 'weight',
			header: 'Доля',
			accessorFn: (p) => Number(p.weight),
			cell: ({ row }) => renderComponent(PercentText, { value: row.original.weight }),
			meta: RIGHT
		},
		{
			id: 'yield',
			header: 'Доходность',
			accessorFn: (p) => amount(p.yield_abs),
			cell: ({ row }) => renderSnippet(earned, row.original),
			sortUndefined: 'last',
			meta: RIGHT
		}
	]);
</script>

{#snippet price(position: Position)}
	{#if position.current_price}
		<MoneyText money={position.current_price} />
	{:else}
		—
	{/if}
{/snippet}

{#snippet value(position: Position)}
	<MoneyText money={position.value_rub} />
	{#if position.value.currency !== position.value_rub.currency}
		<span class="block text-xs text-muted-foreground"><MoneyText money={position.value} /></span>
	{/if}
{/snippet}

{#snippet earned(position: Position)}
	{#if position.yield_abs}
		<MoneyText money={position.yield_abs} signed colorize />
		{#if position.yield_pct !== null}
			<span class="block text-xs">
				<PercentText value={position.yield_pct} signed colorize />
			</span>
		{/if}
	{:else}
		—
	{/if}
{/snippet}

<section aria-labelledby="positions-title" class="space-y-2">
	<h2 id="positions-title" class="text-xs tracking-wider text-muted-foreground uppercase">
		Позиции
	</h2>
	<DataTable {columns} rows={positions} sort={[{ id: 'value_rub', desc: true }]} dense>
		{#snippet empty()}Позиций нет{/snippet}
	</DataTable>
</section>
