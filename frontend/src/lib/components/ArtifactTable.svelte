<script lang="ts">
	import type { ColumnDef, SortingFn } from '@tanstack/table-core';
	import type { TableSpec } from '$lib/types';
	import { renderComponent } from '$lib/ui/data-table';
	import * as Table from '$lib/ui/table';
	import { formatDate, formatMoney, formatNumber, formatPercent } from '$lib/utils/format';
	import DataTable from './DataTable.svelte';
	import InstrumentBadge from './InstrumentBadge.svelte';

	type Row = TableSpec['rows'][number];
	type Column = TableSpec['columns'][number];

	let { spec }: { spec: TableSpec } = $props();

	const NUMERIC = new Set<Column['type']>(['number', 'money', 'percent']);

	/** A cell as the column type shows it; the API sends DecimalStr and ISO dates (§9.9). */
	function show(value: string | null | undefined, column: Column): string {
		if (value === null || value === undefined) return '—';
		switch (column.type) {
			case 'number':
				return formatNumber(value, column.digits ?? undefined);
			case 'money':
				return formatMoney(value, column.currency ?? 'RUB');
			case 'percent':
				return formatPercent(value, { digits: column.digits ?? 2 });
			case 'date':
				return formatDate(value);
			default:
				return value;
		}
	}

	// Numbers sort by value; an empty cell goes last either way.
	const byNumber: SortingFn<Row> = (a, b, id) => {
		const [x, y] = [a.getValue<string | null>(id), b.getValue<string | null>(id)];
		if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1;
		return Number(x) - Number(y);
	};

	const columns = $derived(
		spec.columns.map((column): ColumnDef<Row> => ({
			id: column.key,
			header: column.label,
			// An instrument column sorts by the name the reader sees.
			accessorFn: (row) => {
				const value = row[column.key] ?? null;
				return column.type === 'instrument' && value !== null
					? (spec.instruments[value]?.name ?? value)
					: value;
			},
			cell: ({ row }) => {
				const value = row.original[column.key];
				const instrument =
					column.type === 'instrument' && value ? spec.instruments[value] : undefined;
				return instrument ? renderComponent(InstrumentBadge, { instrument }) : show(value, column);
			},
			sortingFn: NUMERIC.has(column.type) ? byNumber : 'text',
			sortUndefined: 'last',
			meta: { class: NUMERIC.has(column.type) ? 'text-right' : undefined }
		}))
	);
</script>

{#snippet totalRow()}
	<Table.Row>
		{#each spec.columns as column (column.key)}
			{@const value = spec.total?.[column.key]}
			<Table.Cell class={NUMERIC.has(column.type) ? 'text-right font-medium' : 'font-medium'}>
				{value === undefined ? '' : show(value, column)}
			</Table.Cell>
		{/each}
	</Table.Row>
{/snippet}

<figure class="space-y-2">
	<figcaption class="text-sm font-medium">{spec.title}</figcaption>
	<DataTable {columns} rows={spec.rows} dense footer={spec.total ? totalRow : undefined} />
	{#if spec.note}
		<p class="text-xs text-muted-foreground">{spec.note}</p>
	{/if}
</figure>
