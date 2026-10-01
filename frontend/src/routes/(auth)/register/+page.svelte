<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import { Label } from '$lib/ui/label';

	// The CLI prints links like /register?invite=<code> (tech.md §13.3).
	let invite = $state(page.url.searchParams.get('invite') ?? '');
	let email = $state('');
	let name = $state('');
	let password = $state('');
	let pending = $state(false);
	let error = $state<ApiError | null>(null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		pending = true;
		error = null;
		const body = {
			email,
			password,
			invite_code: invite.trim() || null,
			display_name: name.trim() || null
		};
		try {
			await ok(api.POST('/api/auth/register', { body }));
			await goto(resolve('/chat'));
		} catch (failure) {
			error = failure as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<svelte:head><title>Регистрация · Kōri</title></svelte:head>

<form class="space-y-5" onsubmit={submit}>
	<h1 class="text-2xl">Регистрация</h1>
	{#if error}
		<Alert.Root variant="destructive"><Alert.Title>{error.message}</Alert.Title></Alert.Root>
	{/if}
	<div class="space-y-2">
		<Label for="invite">Код приглашения</Label>
		<Input id="invite" autocomplete="off" spellcheck={false} bind:value={invite} />
	</div>
	<div class="space-y-2">
		<Label for="email">Email</Label>
		<Input id="email" type="email" autocomplete="email" required bind:value={email} />
	</div>
	<div class="space-y-2">
		<Label for="name">Имя</Label>
		<Input id="name" autocomplete="name" bind:value={name} />
	</div>
	<div class="space-y-2">
		<Label for="password">Пароль</Label>
		<Input
			id="password"
			type="password"
			autocomplete="new-password"
			minlength={10}
			required
			aria-describedby="password-hint"
			bind:value={password}
		/>
		<p id="password-hint" class="text-xs text-muted-foreground">Не короче 10 символов</p>
	</div>
	<Button type="submit" size="lg" class="w-full" disabled={pending}>
		Зарегистрироваться <span aria-hidden="true">→</span>
	</Button>
	<p class="flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
		Уже есть аккаунт?
		<Button variant="link" class="h-auto px-0" href={resolve('/login')}>Вход</Button>
	</p>
</form>
