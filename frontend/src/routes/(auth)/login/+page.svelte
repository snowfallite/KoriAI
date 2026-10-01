<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, ok } from '$lib/api/client';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { Button } from '$lib/ui/button';
	import { Input } from '$lib/ui/input';
	import { Label } from '$lib/ui/label';

	let email = $state('');
	let password = $state('');
	let pending = $state(false);
	let error = $state<ApiError | null>(null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		pending = true;
		error = null;
		try {
			await ok(api.POST('/api/auth/login', { body: { email, password } }));
			await goto(resolve('/chat'));
		} catch (failure) {
			error = failure as ApiError;
		} finally {
			pending = false;
		}
	}
</script>

<svelte:head><title>Вход · Kōri</title></svelte:head>

<form class="space-y-5" onsubmit={submit}>
	<h1 class="text-2xl">Вход</h1>
	{#if error}
		<Alert.Root variant="destructive"><Alert.Title>{error.message}</Alert.Title></Alert.Root>
	{/if}
	<div class="space-y-2">
		<Label for="email">Email</Label>
		<Input id="email" type="email" autocomplete="email" required bind:value={email} />
	</div>
	<div class="space-y-2">
		<Label for="password">Пароль</Label>
		<Input
			id="password"
			type="password"
			autocomplete="current-password"
			required
			bind:value={password}
		/>
	</div>
	<Button type="submit" size="lg" class="w-full" disabled={pending}>
		Войти <span aria-hidden="true">→</span>
	</Button>
	<p class="flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
		Нет аккаунта?
		<Button variant="link" class="h-auto px-0" href={resolve('/register')}>Регистрация</Button>
	</p>
</form>
