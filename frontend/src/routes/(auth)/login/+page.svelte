<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import AuthField from '../components/AuthField.svelte';
	import AuthPanel from '../components/AuthPanel.svelte';
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
			await goto(resolve('/chat'));
		} catch (error) {
			failure = error as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<svelte:head><title>Вход · Kōri</title></svelte:head>

<AuthPanel title="Вход" note="Email и пароль" error={atField ? null : failure} onsubmit={submit}>
	{#snippet fields()}
		<AuthField id="email" label="Email" error={errorOf('email')}>
			<Input
				id="email"
				type="email"
				autocomplete="email"
				required
				class="h-11 md:text-[15px]"
				aria-invalid={errorOf('email') ? true : undefined}
				aria-describedby={errorOf('email') ? 'email-error' : undefined}
				bind:value={email}
			/>
		</AuthField>
		<AuthField id="password" label="Пароль" error={errorOf('password')}>
			{#snippet aside()}
				<Button
					variant="link"
					class="text-caption"
					aria-controls="password"
					onclick={() => (shown = !shown)}>{shown ? 'Скрыть' : 'Показать'}</Button
				>
			{/snippet}
			<Input
				id="password"
				type={shown ? 'text' : 'password'}
				autocomplete="current-password"
				required
				class="h-11 md:text-[15px]"
				aria-invalid={errorOf('password') ? true : undefined}
				aria-describedby={errorOf('password') ? 'password-error' : undefined}
				bind:value={password}
			/>
		</AuthField>
	{/snippet}
	{#snippet actions()}
		<Button
			variant="secondary"
			size="lg"
			href={resolve('/register')}
			class="min-w-44 flex-1 justify-start"
		>
			<span data-slot="button-glyph" aria-hidden="true">+</span>Регистрация
		</Button>
		<Button type="submit" size="lg" disabled={pending} class="min-w-44 flex-1 justify-start">
			<span data-slot="button-glyph" aria-hidden="true">→</span>Войти
		</Button>
	{/snippet}
</AuthPanel>
