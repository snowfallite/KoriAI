<script lang="ts">
	import type { BrokerAccountOut } from '$lib/types';
	import * as Select from '$lib/ui/select';
	import * as ToggleGroup from '$lib/ui/toggle-group';

	let {
		accounts,
		value,
		onChange
	}: {
		accounts: BrokerAccountOut[];
		/** An account alias; null stands for all accounts. */
		value: string | null;
		onChange: (alias: string | null) => void;
	} = $props();

	// The controls keep a string; aliases match ^acc[0-9]+$, so '*' never collides with one.
	const ALL = '*';
	// Up to four accounts stand as tabs; more go into a list (tech.md §13.2).
	const TABS = 4;
	// A hidden account stays out of the portfolio (tech.md F-01 AC 8).
	const visible = $derived(accounts.filter((account) => !account.is_hidden));
	const current = $derived(visible.find((account) => account.alias === value));
	const name = (account: BrokerAccountOut) => `${account.alias} · ${account.name}`;
	const pick = (next: string) => onChange(next === ALL ? null : next);
</script>

{#if visible.length <= TABS}
	<!-- Tabs in the ink color, the chosen one white; a click on it keeps it. -->
	<ToggleGroup.Root
		type="single"
		variant="outline"
		size="sm"
		aria-label="Счёт"
		bind:value={() => value ?? ALL, (next) => next && pick(next)}
	>
		<ToggleGroup.Item value={ALL} class="px-3">Все счета</ToggleGroup.Item>
		{#each visible as account (account.alias)}
			<ToggleGroup.Item value={account.alias} class="px-3 normal-case"
				>{name(account)}</ToggleGroup.Item
			>
		{/each}
	</ToggleGroup.Root>
{:else}
	<Select.Root type="single" bind:value={() => value ?? ALL, (next) => pick(next)}>
		<Select.Trigger aria-label="Счёт" class="min-w-48">
			{current ? name(current) : 'Все счета'}
		</Select.Trigger>
		<Select.Content>
			<Select.Item value={ALL} label="Все счета" />
			{#each visible as account (account.alias)}
				<Select.Item value={account.alias} label={name(account)} />
			{/each}
		</Select.Content>
	</Select.Root>
{/if}
