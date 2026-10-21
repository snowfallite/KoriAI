<script lang="ts">
	import type { ColumnDef } from '@tanstack/table-core';
	import DataTable from '$lib/components/DataTable.svelte';
	import InstrumentLogo from '$lib/components/InstrumentLogo.svelte';
	import { renderSnippet } from '$lib/ui/data-table';
	import { accountNames } from '$lib/utils/accounts';
	import { cn } from '$lib/utils/cn';
	import { formatMoney, formatNumber, formatPercent } from '$lib/utils/format';
	import { type Account, askHref, type Position, positionQuestion, tickerLine } from '../logic';

	let { positions, accounts }: { positions: Position[]; accounts: Account[] } = $props();

	// The rows of v4 (kori-v4, Портфель): 60 px high, cells 16 px apart, numbers to the right.
	const CELL = 'pr-0 pl-4 in-[tbody]:h-15';
	const RIGHT = `${CELL} text-right`;
	const amount = (money: { amount: string } | null) => (money ? Number(money.amount) : undefined);

	// An account goes by its name (tech.md §13.3); the column shows with more than one account.
	const names = $derived(accountNames(accounts));
	// The bar of a share is as long as the share against the largest one.
	const largest = $derived(Math.max(0, ...positions.map((p) => Number(p.weight))));

	// Numbers sort by value; an empty cell is undefined and goes last both ways.
	const columns = $derived<ColumnDef<Position>[]>([
		{
			id: 'instrument',
			header: 'Инструмент',
			accessorFn: (p) => p.instrument.name,
			cell: ({ row }) => renderSnippet(instrument, row.original),
			meta: { class: 'px-0 in-[tbody]:h-15' }
		},
		...(accounts.length > 1
			? [
					{
						id: 'account',
						header: 'Счёт',
						accessorFn: (p: Position) => names.get(p.account_alias) ?? '—',
						meta: { class: `${CELL} text-muted-foreground` }
					}
				]
			: []),
		{
			id: 'quantity',
			header: 'Кол-во',
			accessorFn: (p) => Number(p.quantity),
			cell: ({ row }) => formatNumber(row.original.quantity),
			meta: { class: `${RIGHT} text-prose` }
		},
		{
			id: 'price',
			header: 'Цена',
			accessorFn: (p) => amount(p.current_price),
			cell: ({ row }) => renderSnippet(price, row.original),
			sortUndefined: 'last',
			meta: { class: `${RIGHT} text-prose` }
		},
		{
			id: 'value_rub',
			header: 'Стоимость',
			accessorFn: (p) => Number(p.value_rub.amount),
			cell: ({ row }) => renderSnippet(value, row.original),
			meta: { class: RIGHT }
		},
		{
			id: 'weight',
			header: 'Доля',
			accessorFn: (p) => Number(p.weight),
			cell: ({ row }) => renderSnippet(share, row.original),
			meta: { class: RIGHT }
		},
		{
			id: 'yield',
			header: 'Результат',
			accessorFn: (p) => amount(p.yield_abs),
			cell: ({ row }) => renderSnippet(result, row.original),
			sortUndefined: 'last',
			meta: { class: RIGHT }
		},
		{
			id: 'ask',
			header: () => renderSnippet(hidden, 'Вопрос'),
			cell: ({ row }) => renderSnippet(ask, row.original),
			enableSorting: false,
			meta: { class: `${RIGHT} w-26` }
		}
	]);
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- askHref gives the chat path with its query -->

{#snippet hidden(text: string)}<span class="sr-only">{text}</span>{/snippet}

{#snippet instrument(position: Position)}
	{@const { name, logo_url } = position.instrument}
	<span class="flex items-center gap-3">
		<InstrumentLogo src={logo_url} {name} size={32} />
		<span class="flex min-w-0 flex-col">
			<span class="truncate text-[14px]/[18px]">{name}</span>
			<span class="text-caption text-grey-600">{tickerLine(position)}</span>
		</span>
	</span>
{/snippet}

{#snippet price(position: Position)}
	{#if position.current_price}
		{formatMoney(position.current_price.amount, position.current_price.currency)}
	{:else}
		—
	{/if}
{/snippet}

{#snippet value(position: Position)}
	<span class="text-[14px]">
		{formatMoney(position.value_rub.amount, position.value_rub.currency, { digits: 0 })}
	</span>
	{#if position.value.currency !== position.value_rub.currency}
		<span class="block text-[12px] text-muted-foreground">
			{formatMoney(position.value.amount, position.value.currency)}
		</span>
	{/if}
{/snippet}

{#snippet share(position: Position)}
	{@const weight = Number(position.weight)}
	<span class="inline-flex flex-col items-end gap-[5px]">
		{formatPercent(position.weight, { digits: 1 })}
		<span aria-hidden="true" class="block h-0.5 w-16 bg-border">
			<span
				class="block h-0.5 bg-grey-400"
				style="width: {largest > 0 ? (Math.max(weight, 0) / largest) * 100 : 0}%"
			></span>
		</span>
	</span>
{/snippet}

<!-- A result from the purchase price: growth in the ink color, a loss in red, always signed; the
     arrow stays with the total of the portfolio (tech.md §13.3). -->
{#snippet result(position: Position)}
	{#if position.yield_abs}
		{@const loss = Number(position.yield_abs.amount) < 0}
		<span class={cn('inline-flex flex-col items-end', loss && 'text-negative')}>
			<span>
				{formatMoney(position.yield_abs.amount, position.yield_abs.currency, {
					signed: true,
					digits: 0
				})}
			</span>
			{#if position.yield_pct !== null}
				<span class={cn('text-[12px]', !loss && 'text-muted-foreground')}>
					{formatPercent(position.yield_pct, { signed: true, digits: 1 })}
				</span>
			{/if}
		</span>
	{:else}
		—
	{/if}
{/snippet}

<!-- The way to the chat shows in every row at rest and turns red with the row (kori-v4). -->
{#snippet ask(position: Position)}
	<a
		href={askHref(positionQuestion(position))}
		aria-label="Спросить о позиции «{position.instrument.name}»"
		class="text-caps text-muted-foreground hover:text-primary focus-visible:text-primary in-[tr:hover]:text-primary"
		>Спросить</a
	>
{/snippet}

<section aria-labelledby="positions-title" class="px-4 pt-12 pb-18 md:px-12">
	<h2 id="positions-title" class="mb-2 flex text-title">
		Позиции<span aria-hidden="true" class="mt-0.5 ml-1.5 text-caption text-muted-foreground"
			>{positions.length}</span
		>
	</h2>
	<DataTable {columns} rows={positions} sort={[{ id: 'value_rub', desc: true }]}>
		{#snippet empty()}Позиций нет{/snippet}
	</DataTable>
</section>
