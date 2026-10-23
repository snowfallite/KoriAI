<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import AuthField from '../components/AuthField.svelte';
	import AuthPanel, { ACTION, FIELD } from '../components/AuthPanel.svelte';
	import { type Field, fieldError } from '../logic';

	const MIN_PASSWORD = 10;

	// The CLI prints links like /register?invite=<code> (tech.md §13.3).
	const fromLink = page.url.searchParams.get('invite');
	let invite = $state(fromLink ?? '');
	let email = $state('');
	let name = $state('');
	let password = $state('');
	let pending = $state(false);
	let failure = $state<ApiError | null>(null);

	// A taken email or a bad invite shows at its field; a closed registration above the fields.
	const atField = $derived(failure ? fieldError(failure) : null);
	const errorOf = (field: Field) => (atField?.field === field ? atField.message : null);
	const described = (...ids: (string | false)[]) => ids.filter(Boolean).join(' ') || undefined;

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		pending = true;
		failure = null;
		const body = {
			email,
			password,
			invite_code: invite.trim() || null,
			display_name: name.trim() || null
		};
		try {
			await ok(api.POST('/api/auth/register', { body }));
			// A new session opens the chat, the home of the app (tech.md §1, F-03).
			await goto(resolve('/chat'));
		} catch (error) {
			failure = error as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<svelte:head><title>Регистрация · Kōri</title></svelte:head>

{#snippet note(text: string)}
	<span class="text-caps text-grey-600">{text}</span>
{/snippet}

<AuthPanel title="Регистрация" compact error={atField ? null : failure} onsubmit={submit}>
	{#snippet fields()}
		<AuthField id="invite" label="Код приглашения" error={errorOf('invite')}>
			{#snippet aside()}
				{#if fromLink}{@render note('из ссылки')}{/if}
			{/snippet}
			<Input
				id="invite"
				autocomplete="off"
				spellcheck={false}
				class="{FIELD} tracking-[0.08em]"
				aria-invalid={errorOf('invite') ? true : undefined}
				aria-describedby={errorOf('invite') ? 'invite-error' : undefined}
				bind:value={invite}
			/>
		</AuthField>
		<AuthField id="name" label="Имя" error={errorOf('name')}>
			{#snippet aside()}{@render note('необязательно')}{/snippet}
			<Input
				id="name"
				autocomplete="nickname"
				class={FIELD}
				aria-invalid={errorOf('name') ? true : undefined}
				aria-describedby={errorOf('name') ? 'name-error' : undefined}
				bind:value={name}
			/>
		</AuthField>
		<AuthField
			id="email"
			label="Email"
			error={errorOf('email')}
			link={failure?.code === 'email_taken'
				? { href: resolve('/login'), label: 'Войти' }
				: undefined}
		>
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
			<Input
				id="password"
				type="password"
				autocomplete="new-password"
				minlength={MIN_PASSWORD}
				required
				class={FIELD}
				aria-invalid={errorOf('password') ? true : undefined}
				aria-describedby={described(!!errorOf('password') && 'password-error', 'password-hint')}
				bind:value={password}
			/>
			{#snippet hint()}
				<p id="password-hint" class="text-caps text-grey-600">Не короче {MIN_PASSWORD} символов</p>
			{/snippet}
		</AuthField>
	{/snippet}
	{#snippet action()}
		<Button type="submit" disabled={pending} class={ACTION}>
			<span data-slot="button-glyph" aria-hidden="true">+</span>Создать аккаунт
		</Button>
	{/snippet}
	{#snippet footer()}
		Уже есть аккаунт? <a href={resolve('/login')}>Войти</a>
	{/snippet}
</AuthPanel>
