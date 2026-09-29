<script lang="ts" generics="T">
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import {
		type ColumnDef,
		type SortingState,
		getCoreRowModel,
		getSortedRowModel
	} from '@tanstack/table-core';
	import type { Snippet } from 'svelte';
	import { FlexRender, createSvelteTable } from '$lib/ui/data-table';
	import * as Table from '$lib/ui/table';
	import { cn } from '$lib/utils/cn';

	let {
		columns,
		rows,
		sort,
		onSortChange,
		onRowClick,
		dense = false,
		empty,
		footer
	}: {
		columns: ColumnDef<T>[];
		rows: T[];
		sort?: SortingState;
		onSortChange?: (sort: SortingState) => void;
		onRowClick?: (row: T) => void;
		dense?: boolean;
		empty?: Snippet;
		/** Rows of the table footer, such as totals. */
		footer?: Snippet;
	} = $props();

	// The parent may own the sort; a click sorts here until the parent passes a new one.
	let sorting = $derived<SortingState>(sort ?? []);

	// Up to 500 rows sort on the client (tech.md §13.2).
	const table = createSvelteTable({
		get data() {
			return rows;
		},
		get columns() {
			return columns;
		},
		state: {
			get sorting() {
				return sorting;
			}
		},
		onSortingChange: (updater) => {
			sorting = typeof updater === 'function' ? updater(sorting) : updater;
			onSortChange?.(sorting);
		},
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel()
	});

	function onKey(event: KeyboardEvent, row: T) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			onRowClick?.(row);
		}
	}
</script>

<Table.Root>
	<Table.Header>
		{#each table.getHeaderGroups() as group (group.id)}
			<Table.Row class="hover:bg-transparent">
				{#each group.headers as header (header.id)}
					{@const sorted = header.column.getIsSorted()}
					<Table.Head
						colspan={header.colSpan}
						aria-sort={sorted === 'asc'
							? 'ascending'
							: sorted === 'desc'
								? 'descending'
								: undefined}
						class={cn(dense && 'h-8', header.column.columnDef.meta?.class)}
					>
						{#if !header.isPlaceholder}
							{#if header.column.getCanSort()}
								<button
									type="button"
									class="inline-flex items-center gap-1 hover:text-muted-foreground"
									onclick={header.column.getToggleSortingHandler()}
								>
									<FlexRender
										content={header.column.columnDef.header}
										context={header.getContext()}
									/>
									{#if sorted === 'asc'}
										<ArrowUp class="size-3" aria-hidden="true" />
									{:else if sorted === 'desc'}
										<ArrowDown class="size-3" aria-hidden="true" />
									{:else}
										<ArrowUpDown class="size-3 opacity-40" aria-hidden="true" />
									{/if}
								</button>
							{:else}
								<FlexRender
									content={header.column.columnDef.header}
									context={header.getContext()}
								/>
							{/if}
						{/if}
					</Table.Head>
				{/each}
			</Table.Row>
		{/each}
	</Table.Header>
	<Table.Body>
		{#each table.getRowModel().rows as row (row.id)}
			<Table.Row
				class={cn(onRowClick && 'cursor-pointer focus-visible:bg-muted focus-visible:outline-none')}
				tabindex={onRowClick ? 0 : undefined}
				onclick={onRowClick ? () => onRowClick(row.original) : undefined}
				onkeydown={onRowClick ? (event) => onKey(event, row.original) : undefined}
			>
				{#each row.getVisibleCells() as cell (cell.id)}
					<Table.Cell class={cn(dense && 'py-1', cell.column.columnDef.meta?.class)}>
						<FlexRender content={cell.column.columnDef.cell} context={cell.getContext()} />
					</Table.Cell>
				{/each}
			</Table.Row>
		{:else}
			<Table.Row class="hover:bg-transparent">
				<Table.Cell colspan={columns.length} class="h-20 text-center text-muted-foreground">
					{#if empty}
						{@render empty()}
					{:else}
						Нет данных
					{/if}
				</Table.Cell>
			</Table.Row>
		{/each}
	</Table.Body>
	{#if footer}
		<Table.Footer>{@render footer()}</Table.Footer>
	{/if}
</Table.Root>
