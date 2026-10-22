<script lang="ts">
	import type { ColumnDef } from '@tanstack/table-core';
	import { invalidate } from '$app/navigation';
	import { SvelteMap } from 'svelte/reactivity';
	import { toast } from 'svelte-sonner';
	import { api, ok } from '$lib/api/client';
	import DataTable from '$lib/components/DataTable.svelte';
	import type { ApiError } from '$lib/types';
	import { renderSnippet } from '$lib/ui/data-table';
	import { Switch } from '$lib/ui/switch';
	import { accountNames } from '$lib/utils/accounts';
	import { cn } from '$lib/utils/cn';
	import { formatDate } from '$lib/utils/format';
	import { type Account, accountNote } from '../logic';

	let { accounts }: { accounts: Account[] } = $props();

	// An account goes by its name (tech.md §13.3); the alias stays in the API.
	const names = $derived(accountNames(accounts));
	// What a switch asked for, by alias, until the API answers and the layout reloads.
	const asked = new SvelteMap<string, boolean>();

	async function show(account: Account, shown: boolean) {
		asked.set(account.alias, shown);
		try {
			await ok(
				api.PATCH('/api/broker/accounts/{alias}', {
					params: { path: { alias: account.alias } },
					body: { is_hidden: !shown }
				})
			);
			await invalidate('app:me');
		} catch (error) {
			toast.error((error as ApiError).message);
		} finally {
			asked.delete(account.alias);
		}
	}

	// The accounts keep the order of their aliases: the API gives them in the order they came.
	const columns = $derived<ColumnDef<Account>[]>([
		{
			id: 'name',
			header: 'Счёт',
			cell: ({ row }) => renderSnippet(name, row.original),
			enableSorting: false
		},
		// A phone keeps the name and the switch: the opening day matters least.
		{
			id: 'opened',
			header: 'Открыт',
			cell: ({ row }) => (row.original.opened_at ? formatDate(row.original.opened_at) : '—'),
			enableSorting: false,
			meta: { class: 'hidden sm:table-cell' }
		},
		{
			id: 'shown',
			header: 'Показывать',
			cell: ({ row }) => renderSnippet(toggle, row.original),
			enableSorting: false,
			meta: { class: 'text-right' }
		}
	]);
</script>

<!-- A hidden account stays in the list, greyed, with its switch off: the portfolio and the agent
     leave it alone (F-01 AC 8). -->
{#snippet name(account: Account)}
	{@const note = accountNote(account.status)}
	<span class={cn('flex flex-col', account.is_hidden && 'text-muted-foreground')}>
		<span class="text-[14px]/[18px]">{names.get(account.alias)}</span>
		{#if note}
			<span class="text-caption text-grey-600">{note}</span>
		{/if}
	</span>
{/snippet}

{#snippet toggle(account: Account)}
	<Switch
		checked={asked.get(account.alias) ?? !account.is_hidden}
		disabled={asked.has(account.alias)}
		aria-label="Показывать «{names.get(account.alias)}»"
		onCheckedChange={(shown) => show(account, shown)}
	/>
{/snippet}

<DataTable {columns} rows={accounts} />
