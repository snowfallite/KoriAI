<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import AuthField from '../components/AuthField.svelte';
	import AuthPanel, { ACTION, FIELD } from '../components/AuthPanel.svelte';
	import { type Field, fieldError } from '../logic';

	let email = $state('');
	let password = $state('');
	let shown = $state(false);
	let pending = $state(false);
	let failure = $state<ApiError | null>(null);

	// A wrong password shows at its field; too many attempts and the like above the fields.
	const atField = $derived(failure ? fieldError(failure) : null);
	const errorOf = (field: Field) => (atField?.field === field ? atField.message : null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		pending = true;
		failure = null;
		try {
			await ok(api.POST('/api/auth/login', { body: { email, password } }));
			// A new session opens the chat, the home of the app (tech.md §1, F-03).
			await goto(resolve('/chat'));
		} catch (error) {
			failure = error as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<svelte:head><title>Вход · Kōri</title></svelte:head>

<AuthPanel title="Вход" error={atField ? null : failure} onsubmit={submit}>
	{#snippet fields()}
		<AuthField id="email" label="Email" error={errorOf('email')}>
			<Input
				id="email"
				type="email"
				autocomplete="email"
				required
				class={FIELD}
				aria-invalid={errorOf('email') ? true : undefined}
				aria-describedby={errorOf('email') ? 'email-error' : undefined}
				bind:value={email}
			/>
		</AuthField>
		<AuthField id="password" label="Пароль" error={errorOf('password')}>
			<!-- Показать lives inside the field, on its right (kori-v4); the ink at 60 % keeps it AA on
			     the fill of the field, where the grey of the mockup reads 4.3:1. -->
			<div class="relative flex">
				<Input
					id="password"
					type={shown ? 'text' : 'password'}
					autocomplete="current-password"
					required
					class="{FIELD} pr-26 md:pr-28"
					aria-invalid={errorOf('password') ? true : undefined}
					aria-describedby={errorOf('password') ? 'password-error' : undefined}
					bind:value={password}
				/>
				<Button
					variant="link"
					aria-controls="password"
					class="absolute top-0 right-0 h-[52px] px-3.5 text-ui text-foreground/60 hover:text-foreground md:px-4"
					onclick={() => (shown = !shown)}>{shown ? 'Скрыть' : 'Показать'}</Button
				>
			</div>
		</AuthField>
	{/snippet}
	{#snippet action()}
		<Button type="submit" disabled={pending} class={ACTION}>
			<span data-slot="button-glyph" aria-hidden="true">→</span>Войти
		</Button>
	{/snippet}
	{#snippet footer()}
		Нет аккаунта? <a href={resolve('/register')}>Регистрация по приглашению</a>
	{/snippet}
</AuthPanel>
