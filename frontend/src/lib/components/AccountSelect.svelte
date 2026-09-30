<script lang="ts">
	import type { BrokerAccountOut } from '$lib/types';
	import * as Select from '$lib/ui/select';

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

	// The select keeps a string; aliases match ^acc[0-9]+$, so '*' never collides with one.
	const ALL = '*';
	// A hidden account stays out of the portfolio (tech.md F-01 AC 8).
	const visible = $derived(accounts.filter((account) => !account.is_hidden));
	const current = $derived(visible.find((account) => account.alias === value));
	const name = (account: BrokerAccountOut) => `${account.alias} · ${account.name}`;
</script>

<Select.Root
	type="single"
	bind:value={() => value ?? ALL, (next) => onChange(next === ALL ? null : next)}
>
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
