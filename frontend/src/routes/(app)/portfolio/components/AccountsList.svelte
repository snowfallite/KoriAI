<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import { formatMoney, formatPercent } from '$lib/utils/format';
	import type { Account } from '../logic';

	let { accounts }: { accounts: Account[] } = $props();

	const isLoss = (account: Account) => Number(account.expected_yield?.amount ?? 0) < 0;

	/** «+53 814 ₽ · +2,52 %»: the result of an account from the purchase prices. */
	function result(account: Account): string {
		const money = account.expected_yield;
		if (!money) return '';
		const amount = formatMoney(money.amount, money.currency, { signed: true, digits: 0 });
		const share = account.expected_yield_pct;
		return share === null ? amount : `${amount} · ${formatPercent(share, { signed: true })}`;
	}
</script>

<!-- Accounts as a list (kori-v3, Портфель): the alias tag, the name, the value and its result. -->
<div>
	<h2 class="border-b pb-3 text-caption uppercase">Счета</h2>
	<ul>
		{#each accounts as account (account.alias)}
			{@const loss = isLoss(account)}
			<li
				class="grid h-[72px] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 border-b border-line-faint"
			>
				<span class="inline-flex h-6 items-center border border-foreground px-2 text-caption">
					{account.alias}
				</span>
				<span class="truncate text-[14px] text-prose">{account.name}</span>
				<span class="flex flex-col items-end gap-1 tabular-nums">
					<span class="text-lead">
						{formatMoney(account.total.amount, account.total.currency, { digits: 0 })}
					</span>
					{#if account.expected_yield}
						<span
							class={cn('text-[12px]/[15px]', loss ? 'text-negative' : 'text-muted-foreground')}
						>
							<span aria-hidden="true">{loss ? '↓' : '↑'}</span>
							{result(account)}
						</span>
					{/if}
				</span>
			</li>
		{/each}
	</ul>
</div>
