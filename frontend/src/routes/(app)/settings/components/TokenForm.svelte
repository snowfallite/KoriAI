<script lang="ts">
	import { invalidate } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import { Label } from '$lib/ui/label';
	import { connectedNote, TOKEN_HELP, tokenError } from '../logic';

	let {
		onConnected,
		onCancel
	}: {
		/** After the API keeps the token and the layout has the new connection. */
		onConnected?: () => void;
		/** Shows Отмена: a connected user changes their mind about a new token. */
		onCancel?: () => void;
	} = $props();

	let token = $state('');
	let pending = $state(false);
	let failure = $state<ApiError | null>(null);

	// A refused token shows at the field; a failure of T-Invest or the server above it.
	const atField = $derived(failure ? tokenError(failure) : null);
	const described = $derived(
		[atField && 'broker-token-error', 'broker-token-hint', 'broker-token-store']
			.filter(Boolean)
			.join(' ')
	);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		pending = true;
		failure = null;
		try {
			const found = await ok(api.PUT('/api/broker/connection', { body: { token } }));
			token = '';
			await invalidate('app:me');
			toast.success(connectedNote(found.accounts.length));
			onConnected?.();
		} catch (error) {
			failure = error as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- the token page of T-Invest is external -->

<!-- The white panel where the person hands over the token (kori-v4, Поле токена): the field with
     its action, and under them the facts about the token, which no other place repeats (F-01
     AC 9). -->
<form class="theme-day bg-background p-4 text-foreground md:p-5" onsubmit={submit}>
	{#if failure && !atField}
		<Alert.Root variant="destructive" class="mb-4">
			<Alert.Title>{failure.message}</Alert.Title>
		</Alert.Root>
	{/if}
	<Label for="broker-token" class="mb-2">Токен Т-Инвестиций</Label>
	<!-- On a narrow phone the action moves under the field rather than squeezing it. -->
	<div class="flex flex-wrap gap-y-2">
		<Input
			id="broker-token"
			type="password"
			autocomplete="off"
			spellcheck={false}
			required
			class="h-11 min-w-48 flex-1 px-3 text-[15px] md:text-[15px]"
			aria-invalid={atField ? true : undefined}
			aria-describedby={described}
			bind:value={token}
		/>
		<Button
			type="submit"
			disabled={pending}
			class="h-11 text-[13px] has-[>[data-slot=button-glyph]]:gap-3.5 has-[>[data-slot=button-glyph]]:pr-[18px]"
		>
			<span data-slot="button-glyph" aria-hidden="true">→</span>Подключить
		</Button>
	</div>
	{#if atField}
		<p id="broker-token-error" role="alert" class="mt-2 text-[13px]/[18px]">{atField}</p>
	{/if}
	<p id="broker-token-hint" class="mt-2.5 text-[13px]/5">
		Нужен токен с доступом «Только чтение». Заявки и переводы сервис не делает. <a
			href={TOKEN_HELP}
			target="_blank"
			rel="noopener noreferrer"
			class="underline underline-offset-3 hover:text-primary-deep">Как выпустить токен</a
		>
	</p>
	<p id="broker-token-store" class="mt-1.5 text-[12px]/[18px] text-grey-600">
		Храним токен зашифрованным и показываем только последние 4 символа.
	</p>
	{#if onCancel}
		<Button
			variant="link"
			class="mt-4 text-ui text-foreground/60 hover:text-foreground"
			onclick={onCancel}>Отмена</Button
		>
	{/if}
</form>
