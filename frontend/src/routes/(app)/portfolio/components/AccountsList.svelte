<script lang="ts">
	import { accountNames } from '$lib/utils/accounts';
	import { cn } from '$lib/utils/cn';
	import { formatMoney } from '$lib/utils/format';
	import { accountResult, type Account } from '../logic';

	let { accounts }: { accounts: Account[] } = $props();

	const names = $derived(accountNames(accounts));
	const isLoss = (account: Account) => Number(account.expected_yield?.amount ?? 0) < 0;
</script>

<!-- Accounts as a list (kori-v4, Портфель): the name, the value and its result to the purchase
     prices; the alias never shows (tech.md §13.3). -->
<div>
	<h2 class="border-b pb-3 text-ui font-bold">Счета</h2>
	<ul>
		{#each accounts as account (account.alias)}
			{@const result = accountResult(account)}
			<li
				class="grid h-[72px] grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 border-b border-line-faint"
			>
				<span class="truncate text-[14px] text-prose">{names.get(account.alias)}</span>
				<span class="flex flex-col items-end gap-1 tabular-nums">
					<span class="text-[18px]/[22px]">
						{formatMoney(account.total.amount, account.total.currency, { digits: 0 })}
					</span>
					{#if result}
						<span
							class={cn(
								'text-[12px]/[15px]',
								isLoss(account) ? 'text-negative' : 'text-muted-foreground'
							)}>{result}</span
						>
					{/if}
				</span>
			</li>
		{/each}
	</ul>
</div>
