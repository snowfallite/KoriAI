<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import { cn } from '$lib/utils/cn';
	import AuthField from '../components/AuthField.svelte';
	import AuthPanel from '../components/AuthPanel.svelte';
	import { type Field, fieldError, lengthHint } from '../logic';

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
			await goto(resolve('/chat'));
		} catch (error) {
			failure = error as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<svelte:head><title>Регистрация · Kōri</title></svelte:head>

{#snippet caption(text: string)}
	<span class="text-caption text-grey-600 uppercase">{text}</span>
{/snippet}

<AuthPanel
	title="Регистрация"
	note="По приглашению"
	error={atField ? null : failure}
	onsubmit={submit}
>
	{#snippet fields()}
		<AuthField id="invite" label="Код приглашения" error={errorOf('invite')}>
			{#snippet aside()}
				{#if fromLink}{@render caption('Из ссылки')}{/if}
			{/snippet}
			<Input
				id="invite"
				autocomplete="off"
				spellcheck={false}
				class={cn('h-11 tracking-[0.08em] md:text-[15px]', fromLink && 'bg-grey-100')}
				aria-invalid={errorOf('invite') ? true : undefined}
				aria-describedby={errorOf('invite') ? 'invite-error' : undefined}
				bind:value={invite}
			/>
		</AuthField>
		<AuthField id="name" label="Имя" error={errorOf('name')}>
			{#snippet aside()}{@render caption('Необязательно')}{/snippet}
			<Input
				id="name"
				autocomplete="nickname"
				class="h-11 md:text-[15px]"
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
				class="h-11 md:text-[15px]"
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
				class="h-11 md:text-[15px]"
				aria-invalid={errorOf('password') ? true : undefined}
				aria-describedby={described(!!errorOf('password') && 'password-error', 'password-hint')}
				bind:value={password}
			/>
			{#snippet hint()}
				<!-- Ten 4 px steps fill as the password grows to its minimum length. -->
				<div aria-hidden="true" class="grid grid-cols-10 gap-0.5">
					{#each { length: MIN_PASSWORD }, i (i)}
						<span class={cn('h-1', i < password.length ? 'bg-foreground' : 'bg-grey-200')}></span>
					{/each}
				</div>
				<p id="password-hint" class="text-caption text-grey-600 uppercase">
					{lengthHint(password.length, MIN_PASSWORD)}
				</p>
			{/snippet}
		</AuthField>
	{/snippet}
	{#snippet actions()}
		<Button
			variant="secondary"
			size="lg"
			href={resolve('/login')}
			class="min-w-44 flex-1 justify-start"
		>
			<span data-slot="button-glyph" aria-hidden="true">→</span>Уже есть аккаунт
		</Button>
		<Button type="submit" size="lg" disabled={pending} class="min-w-44 flex-1 justify-start">
			<span data-slot="button-glyph" aria-hidden="true">→</span>Создать аккаунт
		</Button>
	{/snippet}
</AuthPanel>
