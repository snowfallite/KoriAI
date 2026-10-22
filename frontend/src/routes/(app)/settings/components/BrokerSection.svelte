<script lang="ts">
	import { invalidate } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { api, ok } from '$lib/api/client';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { Badge } from '$lib/ui/badge';
	import { Button } from '$lib/ui/button';
	import * as Card from '$lib/ui/card';
	import { cn } from '$lib/utils/cn';
	import { checkedAt, type Connection } from '../logic';
	import AccountsTable from './AccountsTable.svelte';
	import TokenForm from './TokenForm.svelte';

	let { broker }: { broker: Connection } = $props();

	let replacing = $state(false);
	let checking = $state(false);
	let confirming = $state(false);

	const invalid = $derived(broker.status === 'invalid');
	// A refused token needs a new one at once; a working one only when the user asks.
	const asking = $derived(!broker.connected || invalid || replacing);

	async function check() {
		checking = true;
		try {
			const found = await ok(api.POST('/api/broker/connection/verify'));
			await invalidate('app:me');
			// A refused token shows in the section itself.
			if (found.status === 'active') toast.success('Токен работает');
		} catch (error) {
			toast.error((error as ApiError).message);
		} finally {
			checking = false;
		}
	}

	async function disconnect() {
		try {
			await ok(api.DELETE('/api/broker/connection'));
			replacing = false;
			await invalidate('app:me');
			toast.success('Т-Инвестиции отключены');
		} catch (error) {
			toast.error((error as ApiError).message);
		}
	}
</script>

<!-- The broker section of the settings (kori-v3, Карточки, in the words of v4): a frame with the
     state in its head, the token and its last check, the accounts with their switches and the
     actions under a hairline. -->
<section aria-labelledby="broker-title">
	<Card.Root class="gap-0 py-0">
		<Card.Header class="border-b py-6">
			<h2 id="broker-title" class="text-ui font-bold">Брокер</h2>
			<Card.Description>Т-Инвестиции</Card.Description>
			{#if broker.connected}
				<Card.Action>
					<Badge variant={invalid ? 'destructive' : 'default'}>
						{invalid ? 'Не работает' : 'Подключён'}
					</Badge>
				</Card.Action>
			{/if}
		</Card.Header>
		{#if broker.connected}
			{#if invalid}
				<div class="border-b px-6 py-5">
					<Alert.Root variant="destructive">
						<Alert.Title>Т-Инвестиции не принимают сохранённый токен: подключите новый</Alert.Title>
					</Alert.Root>
				</div>
			{/if}
			<dl class="flex flex-wrap gap-x-16 gap-y-4 border-b px-6 py-5">
				<div>
					<dt class="text-caption text-grey-600">Токен</dt>
					<dd class="mt-1 text-[14px]/5">…{broker.token_hint}</dd>
				</div>
				<div>
					<dt class="text-caption text-grey-600">Проверен</dt>
					<dd class="mt-1 text-[14px]/5">{checkedAt(broker.last_verified_at)}</dd>
				</div>
			</dl>
			<div class="px-4 pt-2 pb-4">
				<AccountsTable accounts={broker.accounts} />
			</div>
		{/if}
		{#if asking}
			<div class={cn('p-4 md:p-6', broker.connected && 'border-t')}>
				<TokenForm
					onConnected={() => (replacing = false)}
					onCancel={replacing ? () => (replacing = false) : undefined}
				/>
			</div>
		{/if}
		{#if broker.connected}
			<Card.Footer class="flex-wrap gap-3 px-6 py-5">
				<Button variant="outline" disabled={checking} onclick={check}>Проверить токен</Button>
				{#if !asking}
					<Button variant="outline" onclick={() => (replacing = true)}>Заменить токен</Button>
				{/if}
				<Button variant="ghost" class="ml-auto" onclick={() => (confirming = true)}
					>Отключить</Button
				>
			</Card.Footer>
		{/if}
	</Card.Root>
</section>

<ConfirmDialog
	bind:open={confirming}
	title="Отключить Т-Инвестиции?"
	description="Токен и список счетов удалятся. Портфель опустеет, пока вы не подключите токен снова."
	confirmLabel="Отключить"
	destructive
	onConfirm={disconnect}
/>
